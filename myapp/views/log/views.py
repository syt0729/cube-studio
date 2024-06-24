from myapp.views.baseSQLA import MyappSQLAInterface
from flask_babel import gettext as __
from flask_babel import lazy_gettext as _
from myapp import app, appbuilder
from myapp.models.log import Log
from . import LogMixin
from flask_appbuilder.views import expose, ModelView

class LogModelView(LogMixin, ModelView):
    datamodel = MyappSQLAInterface(Log)
    list_columns = ['user','method','path','duration_ms','dttm']

    spec_label_columns = {
        "action": _("函数"),
        "path": _("网址"),
        "dttm": _("时间"),
        "duration_ms": _("响应延迟"),
        "referrer": _("相关人"),
    }

if (
    not app.config.get("FAB_ADD_SECURITY_VIEWS") is False
    or app.config.get("MYAPP_LOG_VIEW") is False
):
    appbuilder.add_view(
        LogModelView,
        "Action Log",
        label= "Action Log",
        category="Security",
        category_label= "Security",
        icon="fa-list-ol",
    )





