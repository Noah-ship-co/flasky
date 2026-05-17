from flask import Blueprint

main = Blueprint('main', __name__)

from . import views, errors
from ..models import Permission

# 这是给蓝本 main 注册一个模板上下文处理器。
@main.app_context_processor
def inject_permissions():
    return dict(Permission=Permission)
