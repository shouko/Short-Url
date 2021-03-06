import sys

import ntust_me_mail as MailS
import short_url
import Helper

from urllib.parse import urlparse
from datetime import datetime

from Config import config

from flask import Flask
from flask import request, jsonify, render_template, redirect

from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

app.config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', True)
app.config['SQLALCHEMY_DATABASE_URI'] = config['db_connection_string']

db = SQLAlchemy(app)

class Map(db.Model):
    key = db.Column(db.String(10), primary_key=True)
    url = db.Column(db.Text())
    created = db.Column(db.DateTime())

    def __init__(self, key, url):
        self.key = key
        self.url = url
        self.created = datetime.now()

class Visit(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ip = db.Column(db.String(15))
    visit_time = db.Column(db.DateTime())
    action = db.Column(db.Enum('add', 'go'))

    def __init__(self, ip, action):
        self.ip = ip
        self.action = action
        self.visit_time = datetime.now()

class Email_Apply(db.Model):
    token = db.Column(db.String(65), primary_key=True)
    realname = db.Column(db.String(15))
    username = db.Column(db.String(15))
    email = db.Column(db.String(255))

    def __init__(self, realname, username, email, token):
        self.token = token
        self.realname = realname
        self.username = username
        self.email = email

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/add', methods=['POST'])
@Helper.jsonp
def add():

    # URL Validate
    if request.form['url'].strip() == "":
        return jsonify({'message': 'Url is empty'})
    elif urlparse(request.form['url']).netloc.strip() == '':
        return jsonify({'message': 'Url is illegal'})

    # Usage check
    user_today_usage = len(Visit.query.filter(Visit.action == 'add', Visit.ip == request.environ['REMOTE_ADDR'], Visit.visit_time >= datetime.now().date()).all())
    
    if user_today_usage > config['add_quota_per']:
        return jsonify({'message': 'Today usage is exceed'})

    key = short_url.encode_url(len(Map.query.all()) + config['offset'])
    url = request.form['url']

    exists_query = Map.query.filter_by(url = url).first()
    
    if exists_query != None:
        # If url is exists
        key = exists_query.key
    else:
        db.session.add(Map(key, url))

    db.session.add(Visit(request.environ['REMOTE_ADDR'], 'add'))
    db.session.commit()

    return jsonify({'url': request.url_root + key})

@app.route('/<key>', methods=['GET'])
def go(key):
    result = Map.query.get(key)
    if result == None:
        return jsonify({'message': 'Not Found'})
    else:
        db.session.add(Visit(request.environ['REMOTE_ADDR'], 'go'))
        db.session.commit()

        return redirect(result.url), 200

@app.route('/email/verify', methods=['GET'])
def email_verify():
    applier = Email_Apply.query.get(request.args['token'])

    if applier == None:
        return render_template('email_service_verify.html', message='申請失敗，請聯繫 linroex@ntust.me')
    else:
        password = MailS.get_random_password(12)

        MailS.add_smtp_credentials(applier.username, password)
        MailS.add_forward_route(applier.username, applier.email)

        email = applier.username + '@' + config['DOMAIN']

        MailS.send_mail(email, 'NTUST.ME 電子信箱申請成功通知信', 'success_mail.html', data = {'name': applier.realname, 'email_address': email, 'password': password})

        db.session.delete(applier)
        db.session.commit()

        return render_template('email_service_verify.html', message='申請成功，請檢視信箱，會有相關使用資訊')

if __name__ == '__main__':
    if sys.argv[1] == 'init':
        db.drop_all()
        db.create_all()
    elif sys.argv[1] == 'run':
        app.run(debug = True)
    elif sys.argv[1] == 'migrate':
        db.create_all()
