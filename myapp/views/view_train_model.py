from myapp.views.baseSQLA import MyappSQLAInterface as SQLAInterface
from myapp.models.model_train_model import Training_Model
from myapp.models.model_serving import InferenceService
from myapp.security import MyUser
from myapp.models.model_team import Project, Project_User
from myapp.models.model_train_model import Training_Model
from flask_babel import gettext as __
from flask_babel import lazy_gettext as _
from myapp import app, appbuilder, db
import uuid
from myapp.views.view_team import Project_Join_Filter

from wtforms.validators import DataRequired, Length, Regexp
from wtforms import SelectField, StringField
from flask_appbuilder.fieldwidgets import Select2Widget
from myapp.forms import MyBS3TextFieldWidget
from flask import (
    flash,
    abort,
    g,
    redirect,
    send_file, send_from_directory, request, make_response, jsonify
)
from .base import (
    DeleteMixin,
    MyappFilter,
    MyappModelView,
)
from .baseApi import (
    MyappModelRestApi
)

from flask_appbuilder import expose, action
import datetime, json
import pysnooper
import os
import hashlib
conf = app.config


class Training_Model_Filter(MyappFilter):
    # @pysnooper.snoop()
    def apply(self, query, func):
        user_roles = [role.name.lower() for role in list(self.get_user_roles())]
        if "admin" in user_roles:
            return query
        return query.filter(self.model.created_by_fk == g.user.id)


class Training_Model_ModelView_Base():
    datamodel = SQLAInterface(Training_Model)
    base_permissions = ['can_add', 'can_edit', 'can_delete', 'can_list', 'can_show']
    base_order = ('changed_on', 'desc')
    order_columns = ['id']
    list_columns = ['project_url', 'name', 'version',  'pipeline_url',
                    'creator', 'modified', 'deploy', 'download', 'model_metric', 'framework', 'api_type']
    search_columns = ['created_by', 'project', 'name', 'version', 'framework', 'api_type', 'pipeline_id', 'run_id',
                      'path']
    add_columns = ['project', 'name', 'version', 'describe', 'path', 'framework', 'run_id', 'run_time', 'metrics',
                   'md5', 'api_type', 'pipeline_id']
    edit_columns = add_columns
    show_columns = add_columns
    add_form_query_rel_fields = {
        "project": [["name", Project_Join_Filter, 'org']]
    }
    edit_form_query_rel_fields = add_form_query_rel_fields
    cols_width = {
        "name": {"type": "ellip2", "width": 230},
        "project_url": {"type": "ellip2", "width": 250},
        "pipeline_url": {"type": "ellip2", "width": 230},
        "version": {"type": "ellip2", "width": 200},
        "modified": {"type": "ellip2", "width": 150},
        "deploy": {"type": "ellip2", "width": 100},
        "donwload": {"type": "ellip2", "width": 100},
        "model_metric": {"type": "ellip2", "width": 200},
    }
    spec_label_columns = {
        "path": _("模型文件"),
        "framework": _("训练框架"),
        "api_type": _("推理框架"),
        "deploy": _("发布"),
        "download":_("下载")
    }

    label_title = _('模型')
    base_filters = [["id", Training_Model_Filter, lambda: []]]

    path_describe = _('''
serving：自定义镜像的推理服务，模型地址随意<br>
tfserving：仅支持添加了服务签名的saved_model目录地址，例如：/mnt/xx/../saved_model/<br>
torch-server：torch-model-archiver编译后的mar模型文件，需保存模型结构和模型参数，例如：/mnt/xx/../xx.mar或torch script保存的模型<br>
onnxruntime：onnx模型文件的地址，例如：/mnt/xx/../xx.onnx<br>
triton-server：框架:地址。onnx:模型文件地址model.onnx，pytorch:torchscript模型文件地址model.pt，tf:模型目录地址saved_model，tensorrt:模型文件地址model.plan
'''.strip())

    service_type_choices = [x.replace('_', '-') for x in ['serving','tfserving', 'torch-server', 'onnxruntime', 'triton-server','aihub']]

    add_form_extra_fields = {
        "path": StringField(
            _('模型文件地址'),
            default='/mnt/admin/xx/saved_model/',
            description=path_describe,
            validators=[DataRequired()]
        ),
        "describe": StringField(
            _("描述"),
            description= _('模型描述'),
            validators=[DataRequired()]
        ),
        "pipeline_id": StringField(
            _('任务流id'),
            description= _('任务流的id，0表示非任务流产生模型'),
            default='0'
        ),
        "version": StringField(
            _('版本'),
            widget=MyBS3TextFieldWidget(),
            description= _('模型版本'),
            default=datetime.datetime.now().strftime('v%Y.%m.%d.1'),
            validators=[DataRequired()]
        ),
        "run_id": StringField(
            _('run id'),
            widget=MyBS3TextFieldWidget(),
            description= _('pipeline 训练的run id'),
            default='random_run_id_' + uuid.uuid4().hex[:32]
        ),
        "run_time": StringField(
            _('运行时间'),
            widget=MyBS3TextFieldWidget(),
            description= _('pipeline 训练的 运行时间'),
            default=datetime.datetime.now().strftime('%Y.%m.%d %H:%M:%S'),
        ),
        "name": StringField(
            _("模型名"),
            widget=MyBS3TextFieldWidget(),
            description= _('模型名(a-z0-9-字符组成，最长54个字符)'),
            validators=[DataRequired(), Regexp("^[a-z0-9\-]*$"), Length(1, 54)]
        ),
        "framework": SelectField(
            _('算法框架'),
            description= _("选项xgb、tf、pytorch、onnx、tensorrt等"),
            widget=Select2Widget(),
            choices=[['sklearn','sklearn'],['xgb', 'xgb'], ['tf', 'tf'], ['pytorch', 'pytorch'], ['onnx', 'onnx'], ['tensorrt', 'tensorrt'],['aihub', 'aihub']],
            validators=[DataRequired()]
        ),
        'api_type': SelectField(
            _("部署类型"),
            description= _("推理框架类型"),
            choices=[[x, x] for x in service_type_choices],
            validators=[DataRequired()]
        )
    }
    edit_form_extra_fields = add_form_extra_fields

    # edit_form_extra_fields['path']=FileField(
    #         __('模型压缩文件'),
    #         description=_(path_describe),
    #         validators=[
    #             FileAllowed(["zip",'tar.gz'],_("zip/tar.gz Files Only!")),
    #         ]
    #     )

    # @pysnooper.snoop(watch_explode=('item'))
    def pre_add(self, item):
        if not item.run_id:
            item.run_id = 'random_run_id_' + uuid.uuid4().hex[:32]
        if not item.pipeline_id:
            item.pipeline_id = 0

    def pre_update(self, item):
        if not item.path:
            item.path = self.src_item_json['path']
        self.pre_add(item)

    def checkDownloadAuthorization(self, request_headers):
        _keys = request_headers.keys()
        if 'Username' in _keys and 'Token' in _keys:
            _response_401 = make_response('Authorization failed!')
            _response_401.status_code = 401
            user_name = request_headers['Username']
            token = request_headers['Token']
            password = db.session.query(MyUser).filter_by(username=user_name).first().password
            if not token == hashlib.sha256(password.encode('utf-8')).hexdigest():
                return False
        else:
            return False
        return True
    
    @expose('/dbtest/<params>', methods=['GET'])
    @pysnooper.snoop()
    def dbtest(self, params):
        params = json.loads(params)
        user_name = params['user_name']
        model_name = params['model_name']
        # model_name = '23'
        # model_id = 5
        project_name = 'public'
        # user_name = 'admin'
        model_list = {}

        if not project_name:
            abort(404)

        user_id = db.session.query(MyUser).filter_by(username=user_name).first().id
        project_id = db.session.query(Project).filter_by(name=project_name).first().id
        if not db.session.query(Project_User).filter_by(project_id=project_id).first().user_id == user_id:
            abort(401)
        if model_name:
            train_models = db.session.query(Training_Model).filter_by(name=model_name).all()
        else:
            train_models = db.session.query(Training_Model).filter_by(project=project_id).all()

        if len(train_models) == 0:
            _response = make_response('no model found')
            _response.status_code = 404
            return _response
        for model in train_models:
            id = model.id
            version = model.version
            model_list[id] = version
        return json.dumps(model_list)

    # for api user
    @expose("/query/version/<model_name>", methods=["GET"])
    def query_model_version(self, model_name):
        request_headers = dict(request.headers)
        _response_401 = make_response('Authorization failed!')
        _response_401.status_code = 401
        # if not self.checkDownloadAuthorization(request_headers):
        #     return _response_401

        model_list = {}
        train_models = db.session.query(Training_Model).filter_by(name=model_name).all()
        if len(train_models) == 0:
            _response = make_response('no model found')
            _response.status_code = 404
            return _response
        for model in train_models:
            id = model.id
            version = model.version
            model_list[id] = version
        return json.dumps(model_list)

    # for api user
    @expose("/download/api/<model_id>", methods=["GET"])
    def download_from_api(self, model_id):
        request_headers = dict(request.headers)
        _response_401 = make_response('Authorization failed!')
        _response_401.status_code = 401
        # if not self.checkDownloadAuthorization(request_headers):
        #     return _response_401

        train_model = db.session.query(Training_Model).filter_by(id=model_id).first()
        model_path = train_model.path
        dir_prefix = '/data/k8s/kubeflow/pipeline/workspace/'
        url = dir_prefix
        if model_path.startswith('/mnt'):
            url = os.path.join(dir_prefix, model_path.strip('/mnt'))
        if not os.path.isfile(url):
            url = conf.get('MODEL_URLS', {}).get('train_model', '') # + '?filter=[{"key":"created_by","value":1}]'
            return redirect(url)
        return send_from_directory(os.path.dirname(url), os.path.basename(url), as_attachment=True)

    #for browser user
    @expose("/download/browser/<model_id>", methods=["GET"])
    # @pysnooper.snoop()
    def download_from_browser(self, model_id):
        train_model = db.session.query(Training_Model).filter_by(id=model_id).first()
        model_path = train_model.path
        dir_prefix = '/data/k8s/kubeflow/pipeline/workspace/'
        url = dir_prefix
        if model_path.startswith('/mnt'):
            url = os.path.join(dir_prefix, model_path.strip('/mnt'))
        elif model_path.startswith('http'):
            url = model_path
        if not os.path.isfile(url):
            if url.startswith('https://') or url.startswith('http://'):
                # flash(__('This is a online model, please download from ' + url), 'info')
                return redirect(url)
            else:
                flash(__('model not exist'), 'error')
            url = conf.get('MODEL_URLS', {}).get('train_model', '') # + '?filter=[{"key":"created_by","value":1}]'
            return redirect(url)
        else:
            return send_from_directory(os.path.dirname(url), os.path.basename(url), as_attachment=True)

    @expose("/deploy/<model_id>", methods=["GET", 'POST'])
    def deploy(self, model_id):
        train_model = db.session.query(Training_Model).filter_by(id=model_id).first()
        exist_inference = db.session.query(InferenceService).filter_by(model_name=train_model.name).filter_by(model_version=train_model.version).first()
        from myapp.views.view_inferenceserving import InferenceService_ModelView_base
        inference_class = InferenceService_ModelView_base()
        inference_class.src_item_json = {}
        if not exist_inference:
            exist_inference = InferenceService()
            exist_inference.project_id = train_model.project_id
            exist_inference.project = train_model.project
            exist_inference.model_name = train_model.name
            exist_inference.label = train_model.describe
            exist_inference.model_version = train_model.version
            exist_inference.model_path = train_model.path
            exist_inference.service_type = train_model.api_type
            exist_inference.images = ''
            exist_inference.name = '%s-%s-%s' % (exist_inference.service_type, train_model.name, train_model.version.replace('v', '').replace('.', ''))
            inference_class.pre_add(exist_inference)

            db.session.add(exist_inference)
            db.session.commit()
            flash(__('新服务版本创建完成'), 'success')
        else:
            flash(__('服务版本已存在'), 'success')
        import urllib.parse

        url = conf.get('MODEL_URLS', {}).get('inferenceservice', '') + '?filter=' + urllib.parse.quote(json.dumps([{"key": "model_name", "value": exist_inference.model_name}], ensure_ascii=False))
        print(url)
        return redirect(url)


class Training_Model_ModelView(Training_Model_ModelView_Base, MyappModelRestApi):
    datamodel = SQLAInterface(Training_Model)
    route_base = '/training_model_modelview/web/api'
    add_columns = ['project', 'name', 'version', 'describe', 'path', 'framework', 'metrics','api_type']


appbuilder.add_api(Training_Model_ModelView)


class Training_Model_ModelView_Api(Training_Model_ModelView_Base, MyappModelRestApi):  # noqa
    datamodel = SQLAInterface(Training_Model)
    # base_order = ('id', 'desc')
    route_base = '/training_model_modelview/api'


appbuilder.add_api(Training_Model_ModelView_Api)
