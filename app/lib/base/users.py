from app.lib.models.user import UserModel
from app import db
import flask_bcrypt as bcrypt
import random
import string


class UserManager:
    def __get(self, user_id=None, username=None, email=None):
        query = UserModel.query

        if user_id is not None:
            query = query.filter(UserModel.id == user_id)

        if username is not None:
            query = query.filter(UserModel.username == username)

        if email is not None:
            query = query.filter(UserModel.email == email)

        return query.first()

    def validate_password(self, hash, password):
        return bcrypt.check_password_hash(hash, password)

    def login_session(self, user):
        user.session_token = ''.join(random.choices(string.ascii_lowercase + string.ascii_uppercase + string.digits, k=64))
        db.session.commit()
        db.session.refresh(user)
        return user

    def logout_session(self, user_id):
        user = self.__get(user_id=user_id)
        if user:
            user.session_token = ''
            db.session.commit()
            db.session.refresh(user)
        return True
