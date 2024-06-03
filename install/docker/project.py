from urllib.parse import urlencode
from werkzeug.security import check_password_hash
from flask_appbuilder.security.views import AuthDBView, AuthRemoteUserView
from flask_appbuilder.security.views import expose
from flask_appbuilder.const import LOGMSG_WAR_SEC_LOGIN_FAILED
from flask import send_file, jsonify
from myapp import app
import os
import requests
import logging
from flask import flash, g, redirect, request, session
from flask_login import login_user, logout_user
from flask_appbuilder.security.forms import LoginForm_db
import pysnooper
conf = app.config
ls_domain = conf.get('LABEL_STUDIO_DOMAIN_NAME', 'http://localhost:9002')

# 推送给管理员消息的函数
def push_admin(message):
    pass


# 推送消息给用户的函数
def push_message(receivers, message, link=None):
    pass

class MyCustomRemoteUserView(AuthRemoteUserView):
    pass

# label studio注册新用户，并获取用户token
@pysnooper.snoop(prefix="signup_labelStudio here.............: ")
def signup_labelStudio(email,password):
    payload = {
            'email':  email,
            'password': password
    }
    headers = {
        'content-type':'application/x-www-form-urlencoded',
        'Accept': 'application/json',
    }
    response = requests.post(ls_domain+"/user/externalSignup/", data=urlencode(payload), headers=headers)
    rs = response.json()
    return rs.get('token',None)

def update_ls_token(sm, token,user):
    user.ls_token = "Token "+token
    sm.update_user(user)

def logout_labelStudio():
    ls_token = g.user.ls_token
    headers = {
        'content-type':'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        'Authorization': ls_token
    }
    requests.post(ls_domain+"/user/external_logout/", headers=headers)    

# 账号密码登录方式的登录界面
class Myauthdbview(AuthDBView):
    login_template = "appbuilder/general/security/login_db.html"
    @expose("/login/api/", methods=["GET", "POST"])
    @pysnooper.snoop(watch_explode=('form',))
    def login_api(self):
        request_data = request.args.to_dict()
        if request.get_json(silent=True):
            request_data.update(request.get_json(silent=True))
        token = request_data.get('token', '')
        uuid = request_data.get('uuid', '')
        if token:
            user = self.appbuilder.sm.find_user(token)
            if user:
                login_user(user, remember=True)
                if uuid:
                    user.org = uuid
                    from myapp import db, app
                    db.session.commit()

                return jsonify({
                    "status": 0,
                    "message": '登录成功',
                    "result": {}
                })
            else:
                return jsonify({
                    "status": 1,
                    "message": '未发现用户',
                    "result": {}
                })
   
    @pysnooper.snoop(prefix="login here.............: ")
    @expose("/login/", methods=["GET", "POST"])
    def login(self):
        request_data = request.args.to_dict()
        comed_url = request_data.get('login_url', '')      
        if 'rtx' in request_data:
            if request_data.get('rtx'):
                username = request_data.get('rtx')
                user = self.appbuilder.sm.find_user(username)
                if user:
                    login_user(user, remember=True)
                    if comed_url:
                        return redirect(comed_url)
                    return redirect(self.appbuilder.get_url_for_index)

        if g.user is not None and g.user.is_authenticated:
            return redirect(self.appbuilder.get_url_for_index)

        form = LoginForm_db()
        # 如果提交请求。就是认证
        if form.validate_on_submit():
            username = form.username.data
            import re
            if not re.match('^[a-z][a-z0-9\-]*[a-z0-9]$',username):
                flash('用户名只能由小写字母、数字、-组成',"warning")
                return redirect(self.appbuilder.get_url_for_login)

            # 密码加密
            password = form.password.data
            print("The message was: ", password)

            user = self.appbuilder.sm.find_user(username=username)
            if user is None:
                user = self.appbuilder.sm.find_user(email=username)
            if user is None or (not user.is_active):
                logging.info(LOGMSG_WAR_SEC_LOGIN_FAILED.format(username))
                user = None
            elif check_password_hash(user.password, password):
                self.appbuilder.sm.update_user_auth_stat(user, True)
            elif user.password == password:
                self.appbuilder.sm.update_user_auth_stat(user, True)
            else:
                self.appbuilder.sm.update_user_auth_stat(user, False)
                logging.info(LOGMSG_WAR_SEC_LOGIN_FAILED.format(username))
                user = None

            if not user:
                user = self.appbuilder.sm.find_user(form.username.data)
                if user:
                    # 有用户，但是密码不对
                    flash('发现用户%s已存在，但输入密码不对' % form.username.data, "warning")

                    return redirect(self.appbuilder.get_url_for_login)
                else:
                    # 没有用户的时候自动注册用户
                    user = self.appbuilder.sm.auth_user_remote_org_user(username=form.username.data, org_name='',
                                                                        password=form.password.data)
                    flash('发现用户%s不存在，已自动注册' % form.username.data, "warning")
            login_user(user, remember=True)
            # 添加到public项目组
            from myapp.security import MyUserRemoteUserModelView_Base
            user_view = MyUserRemoteUserModelView_Base()
            user_view.post_add(user)

            # 每次登录都重新获取ls_token值
            token = signup_labelStudio(user.email, password)
            update_ls_token(self.appbuilder.sm, token,user)
            return redirect(comed_url if comed_url else self.appbuilder.get_url_for_index)
        return self.render_template(
            self.login_template, title=self.title, form=form, appbuilder=self.appbuilder
        )

    @expose('/logout')
    def logout(self):
        login_url = request.host_url.strip('/') + '/login/'
        session.pop('user', None)
        g.user = None
        logout_user()
        # label studio 退出登录

        return redirect(login_url)