import os
SQLALCHEMY_DATABASE_URI = os.getenv('MYSQL_SERVICE','')
