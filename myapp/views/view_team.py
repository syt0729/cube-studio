import re

from myapp.security import MyUser
from flask import flash, g, request
from myapp.views.baseSQLA import MyappSQLAInterface as SQLAInterface
from flask_babel import gettext as __
from flask_babel import lazy_gettext as _
from myapp.models.model_team import Project, Project_User
from wtforms import SelectField, StringField
from myapp.utils import core
from myapp import appbuilder, conf
from wtforms.ext.sqlalchemy.fields import QuerySelectField
from flask_appbuilder.fieldwidgets import Select2Widget, BS3TextFieldWidget
from myapp.exceptions import MyappException
from myapp import db, security_manager
from myapp.forms import MyBS3TextFieldWidget, MyBS3TextAreaFieldWidget
from wtforms.validators import DataRequired
from flask_appbuilder.fieldwidgets import Select2ManyWidget
from wtforms.ext.sqlalchemy.fields import QuerySelectMultipleField
from sqlalchemy.exc import IntegrityError
from flask import (
    flash,
    g,
    abort
)
import pysnooper
from .base import (
    get_user_roles,
    MyappFilter,
    MyappModelView,
)
from .baseApi import (
    MyappModelRestApi,
    expose
)
import json
from flask_appbuilder import CompactCRUDMixin
from flask_appbuilder.actions import action
from myapp.utils.py.py_k8s import K8s
# # 获取某类project分组
# class Project_users_Filter(MyappFilter):
#     # @pysnooper.snoop()
#     def apply(self, query, value):
#         # user_roles = [role.name.lower() for role in list(get_user_roles())]
#         # if "admin" in user_roles:
#         #     return query.filter(Project.type == value).order_by(Project.id.desc())
#         return query.filter(self.model.field == value)

# 自己是创建者的才显示,id排序显示
class Creator_Filter(MyappFilter):
    # @pysnooper.snoop()
    def apply(self, query, func):
        user_roles = [role.name.lower() for role in list(self.get_user_roles())]
        if "admin" in user_roles:
            return query.order_by(self.model.id.desc())

        return query.filter(self.model.created_by_fk == g.user.id).order_by(self.model.id.desc())

# 获取自己参加的某类project分组
class Project_Join_Filter(MyappFilter):
    # @pysnooper.snoop()
    def apply(self, query, value):
        if g.user.is_admin():
            return query.filter(self.model.type == value).order_by(self.model.id.desc())
        join_projects_id = security_manager.get_join_projects_id(db.session)
        return query.filter(self.model.id.in_(join_projects_id)).filter(self.model.type==value).order_by(self.model.id.desc())

class Project_Filter(MyappFilter):
    # @pysnooper.snoop()
    def apply(self, query, value):
        project_id = request.args.get('info')
        return query.filter(self.model.id == project_id).order_by(self.model.id.desc())


class ExcludeProjectUsersFilter(MyappFilter):
    def apply(self, query, value):
        project_id = request.args.get('info')

        # 获取当前项目组的用户ID
        existing_user_ids = db.session.query(Project_User.user_id).filter_by(project_id=project_id).all()
        existing_user_ids = [user_id[0] for user_id in existing_user_ids]

        # 返回不在当前项目组的用户
        return query.filter(MyUser.id.notin_(existing_user_ids))

# table show界面下的
class Project_User_ModelView_Base():
    label_title = _('组成员')
    datamodel = SQLAInterface(Project_User)
    add_columns = ['project', 'user', 'role']
    edit_columns = add_columns
    list_columns = ['user', 'role']

    add_form_query_rel_fields = {
        "project": [["name", Project_Filter, 'org']],
        "user": [["name", ExcludeProjectUsersFilter, 'user']]
    }

    # base_filters = [["id", Project_users_Filter, __('org')]]
    add_readonly = {
        "project":True
    }
    edit_readonly = {
        "project":True,
        "user":True
    }
    add_form_extra_fields = {
        "project": QuerySelectField(
             _('项目组'),
            query_factory=lambda: db.session.query(Project),
            allow_blank=False,  # 如果项目是固定的，可以设置为 False 以避免空选项
            widget=Select2Widget(extra_classes="readonly")
        ),
        "user": QuerySelectMultipleField(
            _('用户'),
            query_factory=lambda: db.session.query(MyUser),
            allow_blank=True,
            widget=Select2ManyWidget(extra_classes="readonly"),
            description= _('只有creator可以添加修改组成员，可以添加多个creator'),
        ),
        "role": SelectField(
            _('成员角色'),
            widget=Select2Widget(),
            default='dev',
            choices=[[x, x] for x in ['dev', 'ops', 'creator']],
            description= _('只有creator可以添加修改组成员，可以添加多个creator'),
            validators=[DataRequired()]
        )
    }
    edit_form_extra_fields = add_form_extra_fields

    # @pysnooper.snoop()
    def is_creator(self, proj_id):
        user_roles = [role.name.lower() for role in list(get_user_roles())]
        if "admin" in user_roles:
            return True
        creators = db.session().query(Project_User).filter_by(project_id=proj_id).all()
        for i in range(0, len(creators)):
            if (creators[i].role) == 'creator':
                creators[i] = creators[i].user.username
            else:
                creators[i] = ''
        if g.user.username not in creators:
            return False
        else:
            return True
    
    # @pysnooper.snoop()
    def check_edit_permission(self, item):
        if self.is_creator(item.project_id):
            return True
        else:
            return False
        
    def pre_add_req(self,req_json):
        if self.is_creator(req_json.get('project')):
            return req_json
        else:
            raise MyappException('only creator can add/edit user')

    # @pysnooper.snoop()
    def check_delete_permission(self,item):
        user_roles = [role.name.lower() for role in list(get_user_roles())]
        role = (db.session().query(Project_User).filter_by(project_id = item.project_id)
                                                .filter_by(user_id = g.user.id).first()).role
        if "admin" in user_roles or role == 'creator':
            return True
        return False

    @action("muldelete", "删除", "确定删除所选记录?", "fa-trash", single=False)
    # @pysnooper.snoop(prefix='team_muldel')
    def muldelete(self, items):
        if not items or not items[0]:
            abort(404)
        success = []
        fail = []
        if not self.is_creator(items[0].project_id):
            flash('only creator can delete user', 'error')
            return json.dumps(
                {
                    "success": [],
                    "fail": ['no permit to delete']
                }, indent=4, ensure_ascii=False
            )
        try:
            for item in items:
                try:
                    self.pre_delete(item)
                    db.session.delete(item)
                    success.append(item.to_json())
                except Exception as e:
                    flash(str(e), "danger")
                    fail.append(item.to_json())
            db.session.commit()
        except Exception as e:
            # 捕获其他未预见的异常
            db.session.rollback()
            fail.append('error')
            success = []
        # finally:
        #     db.session.remove()
        return json.dumps(
            {
                "success": success,
                "fail": fail
            }, indent=4, ensure_ascii=False
        )

    pre_update_req=pre_add_req

    def add_customize_json_data(self, json_data):
        if "filter_id" in json_data:
                json_data['project'] = json_data["filter_id"]
                del json_data["filter_id"]
        return json_data

class Project_User_ModelView(Project_User_ModelView_Base, CompactCRUDMixin, MyappModelView):
    datamodel = SQLAInterface(Project_User)


appbuilder.add_view_no_menu(Project_User_ModelView)


class Project_User_ModelView_Api(Project_User_ModelView_Base, MyappModelRestApi):
    datamodel = SQLAInterface(Project_User)
    route_base = '/project_user_modelview/api'


appbuilder.add_api(Project_User_ModelView_Api)


# 获取某类project分组
class Project_Filter(MyappFilter):
    # @pysnooper.snoop()
    def apply(self, query, value):
        # user_roles = [role.name.lower() for role in list(get_user_roles())]
        # if "admin" in user_roles:
        #     return query.filter(Project.type == value).order_by(Project.id.desc())
        return query.filter(self.model.type == value).order_by(self.model.id.desc())





# query joined project
def filter_join_org_project():
    query = db.session.query(Project)
    # user_roles = [role.name.lower() for role in list(get_user_roles())]
    # if "admin" in user_roles:
    if g.user.is_admin():
        return query.filter(Project.type == 'org').order_by(Project.id.desc())

    my_user_id = g.user.get_id() if g.user else 0
    owner_ids_query = db.session.query(Project_User.project_id).filter(Project_User.user_id == my_user_id)

    return query.filter(Project.id.in_(owner_ids_query)).filter(Project.type == 'org').order_by(Project.id.desc())


class Project_ModelView_Base():
    label_title = _('项目组')
    datamodel = SQLAInterface(Project)
    base_permissions = ['can_add', 'can_edit', 'can_delete', 'can_list', 'can_show']
    base_order = ('id', 'desc')
    order_columns = ['name']
    list_columns = ['name', 'user', 'type']
    cols_width = {
        "name": {"type": "ellip1", "width": 200},
        "user": {"type": "ellip2", "width": 700},
        "project_user":{"type": "ellip2", "width": 700},
        "job_template": {"type": "ellip2", "width": 700},
        "type": {"type": "ellip1", "width": 200},
    }

    add_columns = ['name', 'describe', 'expand'] # 'cluster','volume_mount','service_external_ip',
    edit_columns = add_columns
    project_type = 'org'


    add_form_extra_fields = {
        'name': StringField(
            label= _('名称'),
            default='',
            description='',
            widget=BS3TextFieldWidget(),
            validators=[DataRequired()]
        ),
        'describe': StringField(
            label= _('描述'),
            default='',
            description='',
            widget=BS3TextFieldWidget(),
            validators=[DataRequired()]
        ),

    }
    edit_form_extra_fields = add_form_extra_fields


    # @pysnooper.snoop()
    def pre_add_web(self):
        self.edit_form_extra_fields['type'] = StringField(
            _('项目分组'),
            description='',
            widget=MyBS3TextFieldWidget(value=self.project_type, readonly=1),
            default=self.project_type,
        )
        self.add_form_extra_fields = self.edit_form_extra_fields

    def pre_update(self, item):
        if not item.type:
            item.type = self.project_type
        if item.expand:
            core.validate_json(item.expand)
            item.expand = json.dumps(json.loads(item.expand), indent=4, ensure_ascii=False)
        user_roles = [role.name.lower() for role in list(get_user_roles())]
        if "admin" in user_roles:
            return
        if not g.user.username in item.get_creators():
            raise MyappException('just creator can add/edit')


    # before update, check permission
    def pre_update_web(self, item):
        self.pre_add_web()

    def check_edit_permission(self,item):
        if not g.user.is_admin() and g.user.username not in item.get_creators():
            return False
        return True
    check_delete_permission = check_edit_permission

    # add project user
    def post_add(self, item):
        if not item.type:
            item.type = self.project_type
        creator = Project_User(role='creator', user=g.user, project=item)
        db.session.add(creator)
        db.session.commit()

    # @pysnooper.snoop()
    def post_list(self, items):
        return core.sort_expand_index(items)

class Project_ModelView_job_template_Api(Project_ModelView_Base, MyappModelRestApi):
    route_base = '/project_modelview/job_template/api'
    datamodel = SQLAInterface(Project)
    project_type = 'job-template'
    base_filters = [["id", Project_Filter, project_type]]
    list_columns = ['name','job_template', 'type']
    label_title = _('模板分组')
    edit_form_extra_fields = {
        'type': StringField(
            _('模板分组'),
            description='',
            widget=MyBS3TextFieldWidget(value=project_type, readonly=1),
            default=project_type,
        ),
        'expand': StringField(
            _('扩展'),
            description= _('扩展参数。示例参数：<br>"index": 0   表示在pipeline编排中的模板列表的排序位置'),
            widget=MyBS3TextAreaFieldWidget(),
            default='{}',
        )
    }
    add_form_extra_fields = edit_form_extra_fields
    

    def pre_add_req(self, req_json):
        user_roles = [role.name.lower() for role in list(get_user_roles())]
        if "admin" in user_roles:
            return req_json
        else:
            raise MyappException('only admin can add')

    # @pysnooper.snoop()
    def check_delete_permission(self, item):
        # creatros = item.get_creators()
        if not g.user.is_admin():
            return False
        return True

    @action("muldelete", "删除", "确定删除所选记录?", "fa-trash", single=False)
    # @pysnooper.snoop(prefix='job_template_muldel')
    def muldelete(self, items):
        if not items:
            abort(404)
        success = []
        fail = []
        if not g.user.is_admin():
            flash('only admin can delete', 'error')
            return json.dumps(
                {
                    "success": [],
                    "fail": ['only admin can delete']
                }, indent=4, ensure_ascii=False
            )
        try:
            for item in items:
                try:
                    self.pre_delete(item)
                    db.session.delete(item)
                    success.append(item.to_json())
                except Exception as e:
                    flash(str(e), "danger")
                    fail.append(item.to_json())
            db.session.commit()
        except Exception as e:
            # 捕获其他未预见的异常
            db.session.rollback()
            fail.append('error')
            success = []
        # finally:
        #     db.session.remove()
        return json.dumps(
            {
                "success": success,
                "fail": fail
            }, indent=4, ensure_ascii=False
        )

appbuilder.add_api(Project_ModelView_job_template_Api)


class Project_ModelView_org_Api(Project_ModelView_Base, MyappModelRestApi):
    route_base = '/project_modelview/org/api'
    datamodel = SQLAInterface(Project)
    project_type = 'org'
    base_filters = [["id", Project_Join_Filter, project_type]]
    list_columns = ['name', 'project_user', 'type']
    related_views = [Project_User_ModelView_Api, ]
    label_title = _('项目分组')
    edit_form_extra_fields = {
        'type': StringField(
            _('项目分组'),
            description='',
            widget=MyBS3TextFieldWidget(value=project_type, readonly=1),
            default=project_type,
        ),
        'expand': StringField(
            _('扩展'),
            description= _('扩展参数。示例参数：<br>"cluster": "dev"<br>"org": "public"<br>"volume_mount": "kubeflow-user-workspace(pvc):/mnt/;/data/k8s/../group1(hostpath):/mnt1"<br>"SERVICE_EXTERNAL_IP":"xx.内网.xx.xx|xx.公网.xx.xx"'),
            widget=MyBS3TextAreaFieldWidget(),
            default=json.dumps({"cluster": "dev", "org" : "public"}, indent=4, ensure_ascii=False),
        )
    }
    add_form_extra_fields = edit_form_extra_fields

    expand_columns = {
        "expand": {
            "cluster": SelectField(
                label= _('集群'),
                widget=Select2Widget(),
                default='dev',
                description= _('使用该项目组的所有任务部署到的目的集群'),
                choices=[[x, x] for x in list(conf.get('CLUSTERS', {"dev": {}}).keys())],
                validators=[DataRequired()]
            ),
            'volume_mount': StringField(
                label= _('挂载'),
                default='kubeflow-user-workspace(pvc):/mnt/',
                description= _('使用该项目组的所有任务会自动添加的挂载目录，kubeflow-user-workspace(pvc):/mnt/,/data/k8s/../group1(hostpath):/mnt1,nfs-test(storage):/nfs'),
                widget=BS3TextFieldWidget(),
                validators=[]
            ),
            'SERVICE_EXTERNAL_IP': StringField(
                label = _('服务代理ip'),
                default='',
                description = _("服务的代理ip，xx.内网.xx.xx|xx.公网.xx.xx"),
                widget=BS3TextFieldWidget(),
                validators=[]
            ),
            "org": StringField(
                label = _('资源组'),
                widget = BS3TextFieldWidget(),
                default='public',
                description = _('使用该项目组的所有任务部署到的目的资源组，通过机器label org=xx决定'),
                validators=[DataRequired()]
            )
        }
    }

    def pre_add_web(self):
        self.edit_form_extra_fields['type'] = StringField(
            _('项目分组'),
            description='',
            widget=MyBS3TextFieldWidget(value=self.project_type, readonly=1),
            default=self.project_type,
        )
        self.add_form_extra_fields = self.edit_form_extra_fields



appbuilder.add_api(Project_ModelView_org_Api)


class Project_ModelView_train_model_Api(Project_ModelView_Base, MyappModelRestApi):
    route_base = '/project_modelview/model/api'
    datamodel = SQLAInterface(Project)
    project_type = 'model'
    label_title = _('模型分组')
    base_filters = [["id", Project_Filter, project_type]]
    edit_form_extra_fields = {
        'type': StringField(
            _('模型分组'),
            description='',
            widget=MyBS3TextFieldWidget(value=project_type, readonly=1),
            default=project_type,
        )
    }
    add_form_extra_fields = edit_form_extra_fields


appbuilder.add_api(Project_ModelView_train_model_Api)


class Project_ModelView_Api(Project_ModelView_Base, MyappModelRestApi):
    datamodel = SQLAInterface(Project)
    route_base = '/project_modelview/api'
    related_views = [Project_User_ModelView_Api, ]


appbuilder.add_api(Project_ModelView_Api)
