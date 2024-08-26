import datetime
import re
import shutil
import zipfile, pandas
from urllib.parse import urlencode
from flask_appbuilder import action
from myapp.models.model_team import Project, Project_User
from myapp.views.baseSQLA import MyappSQLAInterface as SQLAInterface
from wtforms.validators import DataRequired, Regexp
from myapp import app, appbuilder
from wtforms import StringField, SelectField
from wtforms.ext.sqlalchemy.fields import QuerySelectField
from flask_appbuilder.fieldwidgets import BS3TextFieldWidget, Select2Widget, Select2ManyWidget
from myapp.forms import MyBS3TextAreaFieldWidget, MySelect2Widget, MyCommaSeparatedListField, MySelect2ManyWidget, \
    MySelectMultipleField
from flask import jsonify, Markup, make_response
from .baseApi import MyappModelRestApi
from flask import g, request, redirect
import json, os, sys
from werkzeug.utils import secure_filename
import pysnooper
from sqlalchemy import or_
from sqlalchemy.orm import aliased
from flask_babel import gettext as __
from flask_babel import lazy_gettext as _
import importlib
from myapp.security import MyUser
from .base import (
    DeleteMixin,
    MyappFilter,
    MyappModelView,
)
from myapp import app, appbuilder, db
from flask_appbuilder import expose
from myapp.views.view_team import Project_Join_Filter
from myapp.models.model_dataset import Dataset
import requests
from myapp.utils import core

conf = app.config

from myapp.utils.core import ValidUserListValidator
class Dataset_Filter(MyappFilter):
    # @pysnooper.snoop()
    def apply(self, query, func):
        user_roles = [role.name.lower() for role in list(self.get_user_roles())]
        if "admin" in user_roles:
            return query

        # 当前用户 ID
        user_id = g.user.id

        # 获取与当前用户相关的项目 ID 列表
        related_project_ids = db.session.query(Project.id).join(Project_User).filter(Project_User.user_id == user_id).all()
        related_project_ids = [pid[0] for pid in related_project_ids]

        return query.filter(
            or_(
                self.model.owner.contains(g.user.username),
                self.model.owner.contains('*'),
                self.model.project_id.in_(related_project_ids)
            )
        )


class Dataset_ModelView_base():
    label_title = _('数据集')
    datamodel = SQLAInterface(Dataset)
    base_permissions = ['can_add', 'can_show', 'can_edit', 'can_list', 'can_delete']

    base_order = ("id", "desc")
    order_columns = ['id']
    base_filters = [["id", Dataset_Filter, lambda: []]]  # 设置权限过滤器

    # add_columns = ['name', 'version', 'label', 'describe', 'source_type', 'source', 'field',
    #                'usage', 'storage_class', 'file_type', 'url', 'download_url', 'path',
    #                'storage_size', 'entries_num', 'duration', 'price', 'status', 'icon','project', 'owner', 'features']
    add_columns = ['name', 'version', 'label', 'describe', 'url', 'download_url', 'path', 'icon','project', 'owner', 'features']
    show_columns = ['id', 'name', 'version', 'label', 'describe', 'segment', 'source_type', 'source',
                    'industry', 'field', 'usage', 'storage_class', 'file_type', 'status', 'url',
                    'path', 'download_url', 'storage_size', 'entries_num', 'duration', 'price', 'status', 'icon','project',
                    'owner', 'features']
    search_columns = ['name', 'version', 'label', 'describe', 'source_type', 'source', 'field', 'usage','storage_class', 'file_type', 'status', 'url', 'path', 'download_url']
    spec_label_columns = {
        "subdataset": _("子数据集名称"),
        "source_type": _("来源类型"),
        "source": _("数据来源"),
        "usage": _("数据用途"),
        "research": _("研究方向"),
        "storage_class": _("存储类型"),
        "years": _("数据年份"),
        "url": _("相关网址"),
        "url_html": _("相关网址"),
        "label_html": _("标签"),
        "path": _("本地路径"),
        "path_html": _("本地路径"),
        "entries_num": _("条目数量"),
        "duration": _("文件时长"),
        "price": _("价格"),
        "icon": _("示例图"),
        "icon_html": _("示例图"),
        "ops_html": _("操作"),
        "features": _("特征列"),
        "segment": _("分区")
    }

    edit_columns = add_columns
    # list_columns = ['icon_html', 'name', 'version', 'label', 'describe','project','owner', 'source_type', 'source', 'status',
    #                 'field', 'url_html', 'download_url_html', 'usage', 'storage_class', 'file_type', 'path_html', 'storage_size', 'entries_num', 'price']
    list_columns = ['icon_html', 'name', 'version', 'label_html', 'describe','project', 'owner', 'ops_html', 'path_html', 'download_url_html']
    cols_width = {
        "name": {"type": "ellip1", "width": 150},
        "label": {"type": "ellip2", "width": 200},
        "label_html": {"type": "ellip2", "width": 200},
        "version": {"type": "ellip2", "width": 100},
        "describe": {"type": "ellip2", "width": 300},
        "field": {"type": "ellip1", "width": 100},
        "source_type": {"type": "ellip1", "width": 100},
        "source": {"type": "ellip1", "width": 100},
        "industry": {"type": "ellip1", "width": 100},
        "url_html": {"type": "ellip1", "width": 200},
        "download_url_html": {"type": "ellip1", "width": 200},
        "path_html": {"type": "ellip1", "width": 200},
        "storage_class": {"type": "ellip1", "width": 100},
        "storage_size": {"type": "ellip1", "width": 100},
        "file_type": {"type": "ellip1", "width": 100},
        "project_id": {"type": "ellip1", "width": 200},
        "owner": {"type": "ellip1", "width": 150},
        "status": {"type": "ellip1", "width": 100},
        "entries_num": {"type": "ellip1", "width": 200},
        "duration": {"type": "ellip1", "width": 100},
        "price": {"type": "ellip1", "width": 100},
        "years": {"type": "ellip2", "width": 100},
        "usage": {"type": "ellip1", "width": 200},
        "research": {"type": "ellip2", "width": 100},
        "icon_html": {"type": "ellip1", "width": 100},
        "ops_html": {"type": "ellip1", "width": 150},
    }

    features_demo = '''
    填写规则
{
  "column1": {
    # feature type
    "_type": "dict,list,tuple,Value,Sequence,Array2D,Array3D,Array4D,Array5D,Translation,TranslationVariableLanguages,Audio,Image,Video",

    # data type in dict,list,tuple,Value,Sequence,Array2D,Array3D,Array4D,Array5D
    "dtype": "null,bool,int8,int16,int32,int64,uint8,uint16,uint32,uint64,float16,float32,float64,time32[(s|ms)],time64[(us|ns)],timestamp[(s|ms|us|ns)],timestamp[(s|ms|us|ns),tz=(tzstring)],date32,date64,duration[(s|ms|us|ns)],decimal128(precision,scale),decimal256(precision,scale),binary,large_binary,string,large_string"

    }
}
示例：
{
    "id": {
        "_type": "Value",
        "dtype": "string"
    },
    "image": {
        "_type": "Image"
    },
    "box": {
        "_type": "Value",
        "dtype": "string"
    }
}
    '''
    add_form_extra_fields = {
        "name": StringField(
            label= _('名称'),
            description= _('数据集英文名，小写'),
            default='',
            widget=BS3TextFieldWidget(),
            validators=[DataRequired(), Regexp("^[a-z][a-z0-9_]*[a-z0-9]$"), ]
        ),
        "version": StringField(
            label= _('版本'),
            description= _('数据集版本'),
            default='latest',
            widget=BS3TextFieldWidget(),
            validators=[DataRequired(), Regexp("[a-z0-9_\-]*"), ]
        ),
        "subdataset": StringField(
            label= _('子数据集'),
            description= _('子数据集名称，不存在子数据集，与name同值'),
            default='',
            widget=BS3TextFieldWidget(),
            validators=[]
        ),
        "label": StringField(
            label= _('标签'),
            default='',
            description='',
            widget=BS3TextFieldWidget(),
            validators=[DataRequired()]
        ),
        "describe": StringField(
            label= _('描述'),
            default='',
            description= _('数据集描述'),
            widget=MyBS3TextAreaFieldWidget(),
            validators=[DataRequired()]
        ),
        "industry": SelectField(
            label= _('行业'),
            description= _('行业分类'),
            widget=MySelect2Widget(can_input=True),
            default='',
            choices=[[_(x), _(x)] for x in
                     ['农业', '生物学', '气候+天气', '复杂网络', '计算机网络', '网络安全', '数据挑战', '地球科学', '经济学', '教育', '能源', '娱乐', '金融',
                      'GIS', '政府', '医疗', '图像处理', '机器学习', '博物馆', '自然语言', '神经科学', '物理', '前列腺癌', '心理学+认知', '公共领域', '搜索引擎',
                      '社交网络', '社会科学', '软件', '运动', '时间序列', '交通', '电子竞技']],
            validators=[]
        ),
        "field": SelectField(
            label= _('领域'),
            description='',
            widget=MySelect2Widget(can_input=True),
            choices=[[_(x), _(x)] for x in ['视觉', "语音", "自然语言",'多模态', "风控", "搜索", '推荐','广告']],
            validators=[]
        ),
        "source_type": SelectField(
            label= _('数据源类型'),
            description='',
            widget=Select2Widget(),
            default= _('开源'),
            choices=[[_(x), _(x)] for x in ["开源", "自产", "购买"]],
            validators=[]
        ),
        "source": SelectField(
            label= _('数据来源'),
            description= _('数据来源，可自己填写'),
            widget=MySelect2Widget(can_input=True),
            choices=[[_(x), _(x)] for x in
                     ['github', "kaggle", "ali", 'uci', 'aws', 'google', "company1", "label-team1", "web1"]],
            validators=[]
        ),
        "file_type": MySelectMultipleField(
            label= _('文件类型'),
            description='',
            widget=Select2ManyWidget(),
            choices=[[x, x] for x in ["png", "jpg", 'txt', 'csv', 'wav', 'mp3', 'mp4', 'nv4', 'zip', 'gz']],
        ),
        "storage_class": SelectField(
            label= _('存储类型'),
            description='',
            widget=MySelect2Widget(can_input=True),
            choices=[[_(x), _(x)] for x in ["压缩", "未压缩"]],
        ),
        "storage_size": StringField(
            label= _('存储大小'),
            description='',
            widget=BS3TextFieldWidget(),
        ),
        "project": QuerySelectField(
            label=_('项目组'),
            allow_blank=True,
            widget=Select2Widget(),
            validators=[]
        ),
        "owner": StringField(
            label= _('责任人'),
            default='*',
            description= _('责任人,逗号分隔的多个用户,*表示公开'),
            widget=BS3TextFieldWidget(),
            validators=[DataRequired(),ValidUserListValidator()]
        ),
        "status": SelectField(
            label= _('状态'),
            description= _('数据集状态'),
            widget=MySelect2Widget(can_input=True),
            choices=[[_(x), _(x)] for x in ["损坏", "正常", '未购买', '已购买', '未标注', '已标注', '未校验', '已校验']],
        ),
        "url": StringField(
            label= _('相关网址'),
            description='数据集介绍链接，可点击标签跳转',
            widget=MyBS3TextAreaFieldWidget(rows=3),
            default=''
        ),
        "path": StringField(
            label= _('本地路径'),
            description='本地文件通过notebook上传到平台内，处理后，压缩成单个压缩文件，每行一个压缩文件地址',
            widget=MyBS3TextAreaFieldWidget(rows=3),
            default=''
        ),
        "download_url": StringField(
            label= _('下载地址'),
            description='可以直接下载的链接地址，每行一个url',
            widget=MyBS3TextAreaFieldWidget(rows=3),
            default=''
        ),
        "icon": StringField(
            label=_('预览图'),
            default='',
            description=_('可以为图片地址，svg源码，或者帮助文档链接'),
            widget=BS3TextFieldWidget(),
            validators=[]
        ),
        "features": StringField(
            label= _('特征列'),
            description= _('数据集中的列信息，要求数据集中要有data.csv文件用于表示数据集中的全部数据'),
            widget=MyBS3TextAreaFieldWidget(rows=3, tips=Markup('<pre><code>' + features_demo + "</code></pre>")),
            default=''
        )
    }
    edit_form_extra_fields = add_form_extra_fields

    import_data = True
    download_data = True

    def pre_add(self, item):
        if not item.owner:
            item.owner = g.user.username + ",*"
        if not item.icon:
            item.icon = '/static/assets/images/dataset.png'
        if item.icon and '</svg>' in item.icon:
            item.icon = re.sub(r'width="\d+(\.\d+)?(px)?"', f'width="50px"', item.icon)
            item.icon = re.sub(r'height="\d+(\.\d+)?(px)?"', f'height="50px"', item.icon)
        if not item.version:
            item.version = 'latest'
        if not item.subdataset:
            item.subdataset = item.name
        item.features = json.dumps(json.loads(item.features),indent=4,ensure_ascii=False) if item.features else "{}"

    def post_add(self, item):
        self.sync_label_studio(item)

    def pre_delete(self, item):
        self.sync_label_studio(item, 'D')

    # @pysnooper.snoop()
    def _merge_project_users(self, item):
        if item.owner == '*':
            return item.owner
        if item.project and item.project.id:
            project_users = db.session.query(MyUser.username).join(Project_User, Project_User.user_id == MyUser.id).filter(Project_User.project_id == item.project.id).all()
            project_usernames = [user.username for user in project_users]
            # 将 owner 和 project_usernames 合并并去重
            owner_usernames = set(item.owner.split(','))
            combined_usernames = owner_usernames.union(project_usernames)
            full_owner = ",".join(combined_usernames)
            return full_owner

    @pysnooper.snoop()
    def sync_label_studio(self, item, OpType = 'CR'):
            payload = {
                'name': item.name,
                'id': item.id ,
                'OpType': OpType,
                'description': item.describe
            }
            if OpType == "M":
                owner = self.src_item_json.get('owner')
                project_id = self.src_item_json.get('project_id')
                is_project_modified = False
                if item.project == None or not item.project.id:
                    if project_id:
                        is_project_modified = True
                elif project_id != item.project.id:
                    is_project_modified = True
                if owner != item.owner or is_project_modified:
                    payload['owner'] = self._merge_project_users(item)
                    print(item.project.id)
                    print(item.owner)
            elif OpType == 'CR':
                payload['owner'] = self._merge_project_users(item)

            ls_token = g.user.ls_token
            headers = {
                'content-type':'application/x-www-form-urlencoded',
                'Accept': 'application/json',
                'Authorization': ls_token
            }
            ls_domain = conf.get('LABEL_STUDIO_DOMAIN_NAME', 'http://192.168.1.249:9002')
            response = requests.post(ls_domain+"/api/projects/sync-dataset", data=urlencode(payload), headers=headers)
            if OpType == "CR":
                rs = response.json()
                download_url = rs.get('project_dir',None)
                if download_url:
                    dataset = db.session.query(Dataset).filter_by(id=int(item.id)).first()
                    if dataset:
                        # 更新 dodownload_url 字段
                        dataset.download_url = download_url

                        # 提交更改
                        db.session.commit()
                    else:
                        print(f"No dataset found with id {item.id}")

    def pre_update(self, item):
        self.pre_add(item)
        self.sync_label_studio(item, 'M')

    def check_edit_permission(self, item):
        if not g.user.is_admin() and g.user.username != item.created_by.username and g.user.username not in item.owner:
            return False
        return True
    check_delete_permission = check_edit_permission

    # 将外部存储保存到本地存储中心
    @action("save_store", "备份", "备份数据到当前集群?", "fa-trash", single=True, multiple=False)
    # @pysnooper.snoop()
    def save_store(self, dataset):
        from myapp.tasks.async_task import update_dataset
        kwargs = {
            "dataset_id": dataset.id,
        }
        update_dataset.apply_async(kwargs=kwargs)
        # update_dataset(task=None,dataset_id=item.id)

    @expose("/upload/<dataset_id>", methods=["POST"])
    # @pysnooper.snoop()
    def upload_dataset(self, dataset_id):
        dataset = db.session.query(Dataset).filter_by(id=int(dataset_id)).first()
        filename = request.form['filename']
        partition = request.form.get('partition', '')

        print(request.form)
        print(request.files)
        file = request.files['file']
        file_data = file.stream.read()
        data_dir = f'/data/k8s/kubeflow/dataset/{dataset.name}/{dataset.version}'
        os.makedirs(data_dir, exist_ok=True)
        save_path = os.path.join(data_dir, secure_filename(filename))
        current_chunk = int(request.form['current_chunk'])

        if os.path.exists(save_path) and current_chunk == 0:
            os.remove(save_path)
        try:
            with open(save_path, 'ab') as f:
                f.seek(int(request.form['current_offset']))
                f.write(file_data)
        except OSError:
            # log.exception will include the traceback so we can see what's wrong
            print('Could not write to file')
            return make_response(("Not sure why,"" but we couldn't write the file to disk", 500))

        total_chunks = int(request.form['total_chunk'])

        if current_chunk + 1 == total_chunks:
            # This was the last chunk, the file should be complete and the size we expect
            if os.path.getsize(save_path) != int(request.form['total_size']):
                print(f"File {filename} was completed, but has a size mismatch.Was {os.path.getsize(save_path)} but we expected {request.form['total_size']} ")
                return make_response(('Size mismatch', 500))
            else:
                print(f'File {filename} has been uploaded successfully')
                # save_type = request.form['save_type']  # 替换，还是追加数据集
                dataset.path = (dataset.path or '') + "\n" + save_path
                dataset.path = '\n'.join(list(set([x.strip() for x in dataset.path.split('\n') if x.strip()])))
                if partition:
                    segment = json.loads(dataset.segment) if dataset.segment else {}
                    if partition not in segment:
                        segment[partition] = [save_path]
                    else:
                        segment[partition].append(save_path)
                        segment[partition] = list(set(segment[partition]))
                    dataset.segment = json.dumps(segment, indent=4, ensure_ascii=False)
                db.session.commit()
        else:
            print(f'Chunk {current_chunk + 1} of {total_chunks} for file {filename} complete')

        return make_response(("Chunk upload successful", 200))

    # # 将外部存储保存到本地存储中心
    # @expose("/download/<dataset_name>", methods=["GET","POST"])
    # @expose("/download/<dataset_name>/<dataset_version>", methods=["GET",'POST'])
    # def download(self, dataset_name,dataset_version=None):
    #     try:
    #         store_type = conf.get('STORE_TYPE', 'minio')
    #         params = importlib.import_module(f'myapp.utils.store.{store_type}')
    #         store_client = getattr(params, store_type.upper() + '_client')(**conf.get('STORE_CONFIG', {}))
    #         remote_file_path = f'/dataset/{dataset_name}/{dataset_version if dataset_version else "latest"}'
    #         urls = store_client.get_download_url(remote_file_path)
    #
    #         return jsonify({
    #             "status":0,
    #             "result":{
    #                 "store_type": conf.get('STORE_TYPE', 'minio'),
    #                 "download_urls":urls
    #             },
    #             "message":"success"
    #         })
    #     except Exception as e:
    #         print(e)
    #         return jsonify({
    #             "status": 1,
    #             "result": '',
    #             "message": str(e)
    #         })

    # 将外部存储保存到本地存储中心
    @expose("/download/<dataset_id>", methods=["GET", "POST"])
    @expose("/download/<dataset_id>/<partition>", methods=["GET", "POST"])
    def download_dataset(self, dataset_id, partition=''):

        # 生成下载链接
        def path2url(path):
            if 'http://' in path or "https://" in path:
                return path
            if re.match('^/mnt/', path):
                return f'{request.host_url.strip("/")}/static{path}'
            if re.match('^/data/k8s/kubeflow/dataset', path):
                return f'{request.host_url.strip("/")}/static{path.replace("/data/k8s/kubeflow", "")}'

        dataset = db.session.query(Dataset).filter_by(id=int(dataset_id)).first()
        try:
            download_url = []
            if dataset.path and dataset.path.strip():
                # 如果存储在集群数据集中心
                # 如果存储在个人目录
                paths = dataset.path.split('\n')
                for path in paths:
                    download_url.append(path2url(path))

            # 如果存储在外部链接
            elif dataset.download_url and dataset.download_url.strip():
                download_url = dataset.download_url.split('\n')
            else:
                # 如果存储在对象存储中
                store_type = conf.get('STORE_TYPE', 'minio')
                params = importlib.import_module(f'myapp.utils.store.{store_type}')
                store_client = getattr(params, store_type.upper() + '_client')(**conf.get('STORE_CONFIG', {}))
                remote_file_path = f'/dataset/{dataset.name}/{dataset.version}'
                download_url = store_client.get_download_url(remote_file_path)

            if partition:
                segment = json.loads(dataset.segment) if dataset.segment else {}
                if partition in segment:
                    download_url = segment[partition]
                    download_url = [path2url(url) for url in download_url]

            return jsonify({
                "status": 0,
                "result": {
                    "store_type": conf.get('STORE_TYPE', 'minio'),
                    "download_urls": download_url
                },
                "message": "success"
            })
        except Exception as e:
            print(e)
            return jsonify({
                "status": 1,
                "result": '',
                "message": str(e)
            })

    @expose("/preview/<dataset_name>", methods=["GET", "POST"])
    @expose("/preview/<dataset_name>/<dataset_version>", methods=["GET", 'POST'])
    @expose("/preview/<dataset_name>/<dataset_version>/<dataset_segment>", methods=["GET", 'POST'])
    def preview(self):
        _args = request.get_json(silent=True) or {}
        _args.update(request.args)
        _args.update(json.loads(request.args.get('form_data', {})))
        info = {}
        info.update(
            {
                "rows": [
                    {
                        "row_idx": 0,
                        "row": {
                            "col1": "",
                            "col2": "",
                            "col3": "",
                            "label1": [""],
                            "no_answer": False
                        },
                        "truncated_cells": []
                    }
                ]
            }
        )
        return jsonify(info)


class Dataset_ModelView_Api(Dataset_ModelView_base, MyappModelRestApi):
    datamodel = SQLAInterface(Dataset)
    route_base = '/dataset_modelview/api'
    add_form_query_rel_fields = {
        "project": [["name", Project_Join_Filter, 'org']]
    }


appbuilder.add_api(Dataset_ModelView_Api)

