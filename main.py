import base64
import requests
import os
import re
import math
import json
from datetime import datetime, timedelta
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivymd.app import MDApp
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFillRoundFlatButton, MDFlatButton, MDIconButton
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.textfield import MDTextField
from kivy.core.window import Window
from kivy.utils import platform
from kivy.config import Config
from kivy.app import App
# 导入Kivy原生基础弹窗（核心）
from kivy.uix.popup import Popup
import sys
Config.set('kivy', 'log_level', 'error')  # 减少日志输出

# ====================== 强制中文字体配置（确保弹窗中文显示） ======================
from kivy.core.text import LabelBase
def register_chinese_fonts():
    """注册中文字体，兼容Windows/Android"""
    font_paths = []
    if platform == 'win':
        font_paths = [
            'C:/Windows/Fonts/msyh.ttc',      # 微软雅黑
            'C:/Windows/Fonts/simhei.ttf',    # 黑体
            'C:/Windows/Fonts/simsun.ttc',    # 宋体
        ]
    elif platform == 'android':
        font_paths = [
            '/system/fonts/DroidSansFallback.ttf',
            '/system/fonts/NotoSansCJK-Regular.ttc',
            '/system/fonts/SourceHanSansCN-Regular.otf',
        ]
    else:
        font_paths = ['Roboto']
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            LabelBase.register(name='Chinese', fn_regular=font_path)
            Config.set('kivy', 'default_font', ['Chinese', font_path])
            print(f"成功加载中文字体: {font_path}")
            return
    LabelBase.register(name='Chinese', fn_regular='Roboto')
    Config.set('kivy', 'default_font', ['Chinese', 'Roboto'])

register_chinese_fonts()

# ====================== 提前导入腾讯云SDK相关类 ======================
try:
    from tencentcloud.common import credential
    from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
    from tencentcloud.ocr.v20181119 import ocr_client, models
    TENCENT_SDK_AVAILABLE = True
except ImportError as e:
    print(f"腾讯云SDK导入警告: {e}")
    TENCENT_SDK_AVAILABLE = False
    class TencentCloudSDKException(Exception):
        pass

# ====================== 安卓底层适配 ======================
ANDROID_PERMS_GRANTED = False
if platform == 'android':
    try:
        from jnius import autoclass, cast
        from android.permissions import request_permissions, Permission, check_permission
        from android.storage import app_storage_path, primary_external_storage_path
        from android import mActivity
        
        # 强制竖屏
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        activity = PythonActivity.mActivity
        activity.setRequestedOrientation(1)  # SCREEN_ORIENTATION_PORTRAIT
        activity.setRequestedOrientation(activity.SCREEN_ORIENTATION_LOCKED)
        
        # FileProvider
        File = autoclass('java.io.File')
        Uri = autoclass('android.net.Uri')
        FileProvider = autoclass('androidx.core.content.FileProvider')
        Context = autoclass('android.content.Context')
        Intent = autoclass('android.content.Intent')
        
        # 权限列表
        REQUIRED_PERMS = [
            Permission.CAMERA,
            Permission.READ_EXTERNAL_STORAGE,
            Permission.WRITE_EXTERNAL_STORAGE,
            Permission.INTERNET,
            Permission.ACCESS_MEDIA_LOCATION
        ]
    except Exception as e:
        print(f"安卓适配初始化警告: {e}")
        REQUIRED_PERMS = []

# ====================== 配置文件管理 ======================
def get_config_path():
    """获取配置文件存储路径"""
    if platform == 'android':
        try:
            config_dir = os.path.join(app_storage_path(), 'config')
        except:
            config_dir = os.path.join(os.getcwd(), 'config')
    else:
        config_dir = os.path.join(os.getcwd(), 'config')
    
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, 'app_config.json')

def load_config():
    """加载配置文件"""
    default_config = {
        "ocr_secret_id": "",
        "ocr_secret_key": "",
        "webhook_url": "",
        "field_mapping": {
            "no": "ftQMc5",
            "name": "ftk5Tx",
            "qty": "fi17hF",
            "batch": "fHavw8",
            "date": "f04Gwj"
        }
    }
    
    config_path = get_config_path()
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                default_config.update(loaded_config)
                return default_config
    except Exception as e:
        print(f"加载配置失败，使用默认配置: {e}")
    
    return default_config

def save_config(config_data):
    """保存配置文件"""
    try:
        config_path = get_config_path()
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"保存配置失败: {e}")
        return False

# ====================== 核心配置 ======================
WEWORK_CONFIG = load_config()
FIXED_CONFIG = {
    "headers": {"Content-Type": "application/json; charset=utf-8"},
    "success_code": 0,
    "success_msg": "提交到企业微信表格成功!",
    "ocr_expire_minutes": 30,
    "ocr_retry_times": 2
}

# ====================== KV界面（主界面） ======================
KV = '''
FloatLayout:
    canvas.before:
        Color:
            rgba: 0.9, 0.9, 0.9, 1  # 浅灰色背景，避免白色刺眼
        Rectangle:
            pos: self.pos
            size: self.size

    # 右上角设置按钮
    MDIconButton:
        icon: "settings"
        pos_hint: {"right": 0.95, "top": 0.98}
        size_hint: None, None
        size: (50, 50)
        on_press: app.open_settings_dialog()
    
    # 按钮容器
    MDBoxLayout:
        id: btn_container
        orientation: 'horizontal'
        size_hint: 1, 0.15
        pos_hint: {'center_x': 0.5, 'y': 0.1}
        spacing: 20
        padding: [20, 0, 20, 0]
        
        MDFillRoundFlatButton:
            text: "拍照"
            size_hint_y: None
            height: 60
            md_bg_color: "#4CAF50"
            font_size: 20
            font_name: 'Chinese'
            on_press: app.take_photo()
        
        MDFillRoundFlatButton:
            text: "选择照片"
            size_hint_y: None
            height: 60
            md_bg_color: "#2196F3"
            font_size: 20
            font_name: 'Chinese'
            on_press: app.choose_image()
        
        MDFillRoundFlatButton:
            text: "退出"
            size_hint_y: None
            height: 60
            md_bg_color: "#F44336"
            font_size: 20
            font_name: 'Chinese'
            on_press: app.exit_app()
'''

# ====================== 设置对话框布局 ======================
SETTINGS_DIALOG_KV = '''
MDBoxLayout:
    orientation: "vertical"
    spacing: "15dp"
    padding: ["20dp", "20dp", "20dp", "30dp"]
    size_hint: 1, None
    height: self.minimum_height
    pos_hint: {"top": 1}
    
    MDLabel:
        text: "系统配置"
        font_name: "Chinese"
        font_size: 22
        bold: True
        size_hint_y: None
        height: "50dp"
        halign: "center"
    
    # OCR Secret ID
    MDTextField:
        id: ocr_secret_id
        hint_text: "OCR Secret ID"
        font_name: "Chinese"
        size_hint_y: None
        height: "50dp"
        multiline: False
        font_size: 16
        padding: "10dp"
    
    # OCR Secret Key
    MDTextField:
        id: ocr_secret_key
        hint_text: "OCR Secret Key"
        font_name: "Chinese"
        size_hint_y: None
        height: "50dp"
        multiline: False
        font_size: 16
        padding: "10dp"
    
    # Webhook URL
    MDTextField:
        id: webhook_url
        hint_text: "企微表格Webhook URL"
        font_name: "Chinese"
        size_hint_y: None
        height: "50dp"
        multiline: False
        font_size: 16
        padding: "10dp"
    
    # 字段映射配置
    MDTextField:
        id: field_mapping
        hint_text: "字段映射（JSON格式）"
        font_name: "Chinese"
        size_hint_y: None
        height: "100dp"
        multiline: True
        font_size: 14
        padding: "10dp"
    
    # 按钮行
    MDBoxLayout:
        orientation: "horizontal"
        spacing: "30dp"
        size_hint_y: None
        height: "60dp"
        pos_hint: {"center_x": 0.5, "top": 1}
        
        MDFillRoundFlatButton:
            id: save_btn
            text: "保存"
            font_name: "Chinese"
            md_bg_color: "#4CAF50"
            size_hint: (0.4, 1)
            font_size: 18
        
        MDFillRoundFlatButton:
            id: cancel_btn
            text: "取消"
            font_name: "Chinese"
            md_bg_color: "#F44336"
            size_hint: (0.4, 1)
            font_size: 18
'''

# ====================== 可编辑标签 ======================
class EditableLabel(Label):
    def __init__(self, prefix, key, **kwargs):
        kwargs['font_name'] = 'Chinese'
        super().__init__(**kwargs)
        self.prefix = prefix
        self.key = key
        self.content = ""
        self.edit_input = None
        self.app = None

    def update_content(self, new_content):
        self.content = new_content.strip()
        self.text = f"{self.prefix}{self.content}" if self.content else ""

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and not self.edit_input and self.content:
            self._create_edit_input()
            return True
        return super().on_touch_down(touch)

    def _create_edit_input(self):
        x, y = self.pos
        width, height = self.size
        self.edit_input = TextInput(
            text=self.content,
            pos=(x, y),
            size=(width, height),
            size_hint=(None, None),
            font_size=self.font_size,
            font_name='Chinese',
            foreground_color=(1, 0, 0, 1),
            background_color=(1, 1, 1, 0.5),
            cursor_color=(0, 0, 0, 1),
            multiline=False,
            halign=self.halign,
        )
        self.edit_input.bind(on_text_validate=self._save_edit)
        self.edit_input.bind(on_touch_down=self._check_focus_loss)
        self.parent.add_widget(self.edit_input)
        self.edit_input.focus = True
        self.opacity = 0

    def _save_edit(self, *args):
        if not self.edit_input:
            return
        new_content = self.edit_input.text.strip()
        if new_content:
            self.update_content(new_content)
            if self.app:
                self.app.ocr_result[self.key]["text"] = new_content
        self.parent.remove_widget(self.edit_input)
        self.edit_input = None
        self.opacity = 1

    def _check_focus_loss(self, instance, touch):
        if not instance.collide_point(*touch.pos):
            self._save_edit()

# ====================== 主应用 ======================
class ReceiptApp(MDApp):
    title = "点收单识别" 

    ocr_result = {
        "no": {"text":"", "x":0, "y":0, "corrected_x":0, "corrected_y":0},
        "name": {"text":"", "x":0, "y":0, "corrected_x":0, "corrected_y":0},
        "qty": {"text":"", "x":0, "y":0, "corrected_x":0, "corrected_y":0},
        "batch": {"text":"", "x":0, "y":0, "corrected_x":0, "corrected_y":0},
        "date": {"text":"", "x":0, "y":0, "corrected_x":0, "corrected_y":0}
    }
    current_img_path = ""
    preview_layout = None
    img_width = 0
    img_height = 0
    x_slope = 0
    x_intercept = 0
    y_slope = 0
    y_intercept = 0
    correction_ready = False
    # 移除复杂的MDDialog，只用原生Popup
    settings_dialog = None
    ocr_client = None
    ocr_credential = None
    ocr_credential_create_time = None

    def build(self):
        if platform == 'win':
            Window.size = (360, 640)
            Window.minimum_width = 360
            Window.minimum_height = 640
            Window.allow_screensaver = False
            Window.rotation = 0
        
        if platform == 'android':
            Clock.schedule_once(self._request_permissions_safe, 0.1)
        
        return Builder.load_string(KV)

    def _request_permissions_safe(self, *args):
        """安全申请权限"""
        if platform == 'android' and REQUIRED_PERMS:
            request_permissions(REQUIRED_PERMS, self._on_permissions_granted)

    def _on_permissions_granted(self, permissions, results):
        """权限申请结果回调"""
        global ANDROID_PERMS_GRANTED
        ANDROID_PERMS_GRANTED = all(results)
        if not ANDROID_PERMS_GRANTED:
            self.show_dialog("部分权限未授予，部分功能可能无法使用")

    def get_safe_image_path(self):
      """获取安全的图片存储路径"""
      if platform == 'android':
          try:
              # 改用应用私有目录，无需存储权限
              from android.storage import app_storage_path
              img_dir = os.path.join(app_storage_path(), 'ReceiptApp')
              os.makedirs(img_dir, exist_ok=True)
              return os.path.join(img_dir, 'receipt_ocr.jpg')
          except:
              img_dir = os.path.join(os.getcwd(), 'ReceiptApp')
              os.makedirs(img_dir, exist_ok=True)
              return os.path.join(img_dir, 'receipt_ocr.jpg')
      else:
          return os.path.join(os.getcwd(), 'receipt_ocr.jpg')

    def take_photo(self):
        """拍照功能"""
        if platform == 'android' and not check_permission(Permission.CAMERA):
            self.show_dialog("请先授予相机权限")
            self._request_permissions_safe()
            return
        
        self.current_img_path = self.get_safe_image_path()
        
        if platform == 'android':
            try:
                file = File(self.current_img_path)
                context = cast(Context, mActivity.getApplicationContext())
                authority = context.getPackageName() + ".fileprovider"
                content_uri = FileProvider.getUriForFile(context, authority, file)
                context.grantUriPermission(
                    context.getPackageName(),
                    content_uri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                )
            except Exception as e:
                self.show_dialog(f"相机配置错误: {str(e)}")
                return
        
        try:
            from plyer import camera
            Clock.schedule_once(lambda x: camera.take_picture(
                filename=self.current_img_path,
                on_complete=self.on_image_selected
            ), 0.1)
        except Exception as e:
            self.show_dialog(f"相机调用失败: {str(e)}")

    def choose_image(self):
        """选择照片功能"""
        if platform == 'android' and not (check_permission(Permission.READ_EXTERNAL_STORAGE) and check_permission(Permission.WRITE_EXTERNAL_STORAGE)):
            self.show_dialog("请先授予存储权限")
            self._request_permissions_safe()
            return
        
        try:
            from plyer import filechooser
            filechooser.open_file(
                filters=[("图片文件", "*.jpg;*.png;*.jpeg")],
                on_selection=self.on_file_selected
            )
        except Exception as e:
            self.show_dialog(f"打开相册失败: {str(e)}")

    def exit_app(self):
        """退出应用"""
        if platform == 'android':
            try:
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                activity = PythonActivity.mActivity
                activity.finish()
            except:
                App.get_running_app().stop()
        else:
            App.get_running_app().stop()
            sys.exit(0)

    def on_file_selected(self, selection):
        if selection and len(selection) > 0:
            self.on_image_selected(selection[0])

    def on_image_selected(self, img_path):
        """图片选择回调"""
        if not os.path.exists(img_path):
            self.show_dialog("图片文件不存在")
            return
        
        self.current_img_path = img_path
        self.root.ids.btn_container.opacity = 0
        Clock.schedule_once(lambda x: self._load_preview_layout(img_path), 0.1)

    def _load_preview_layout(self, img_path):
        """加载预览界面"""
        self.preview_layout = FloatLayout(size_hint=(1,1))
        
        try:
            from PIL import Image as PILImage
            pil_img = PILImage.open(img_path)
            self.img_width, self.img_height = pil_img.size
        except Exception as e:
            self.show_dialog(f"图片加载失败: {str(e)}")
            self.root.ids.btn_container.opacity = 1
            return
        
        # 添加图片控件
        img_widget = Image(
            source=img_path,
            size_hint=(0.9, 0.7),
            pos_hint={'center_x':0.5, 'center_y':0.6},
            allow_stretch=True,
            keep_ratio=True
        )
        self.preview_layout.add_widget(img_widget)

        # 初始化可编辑标签
        self.no_label = EditableLabel(prefix="单号: ", key="no", size_hint=(None,None), size=(200,30), color=(1,0,0,1), font_size=16, bold=True)
        self.name_label = EditableLabel(prefix="品名: ", key="name", size_hint=(None,None), size=(200,30), color=(1,0,0,1), font_size=16, bold=True)
        self.qty_label = EditableLabel(prefix="数量: ", key="qty", size_hint=(None,None), size=(200,30), color=(1,0,0,1), font_size=16, bold=True)
        self.batch_label = EditableLabel(prefix="批次: ", key="batch", size_hint=(None,None), size=(200,30), color=(1,0,0,1), font_size=16, bold=True)
        self.date_label = EditableLabel(prefix="日期: ", key="date", size_hint=(None,None), size=(200,30), color=(1,0,0,1), font_size=16, bold=True)
        
        self.no_label.app = self
        self.name_label.app = self
        self.qty_label.app = self
        self.batch_label.app = self
        self.date_label.app = self
        
        # 添加标签
        for lbl in [self.no_label, self.name_label, self.qty_label, self.batch_label, self.date_label]:
            self.preview_layout.add_widget(lbl)

        # 添加提交/取消按钮
        btn_box = BoxLayout(size_hint=(0.8, None), height=60, pos_hint={'center_x':0.5, 'y':0.1}, spacing=10)
        self.submit_btn = MDFillRoundFlatButton(
            text="提交到企微表格",
            size_hint=(0.7, 1),
            md_bg_color="#FF9800", 
            font_size=20,
            font_name='Chinese',
            on_press=self.submit_to_wework_table
        )
        self.cancel_btn = MDFillRoundFlatButton(
            text="取消",
            size_hint=(0.3, 1),
            md_bg_color="#F44336", 
            font_size=16,
            font_name='Chinese',
            on_press=self.cancel_operation
        )
        
        btn_box.add_widget(self.submit_btn)
        btn_box.add_widget(self.cancel_btn)
        self.preview_layout.add_widget(btn_box)
        self.root.add_widget(self.preview_layout)
        
        Clock.schedule_once(lambda x: self.ocr_recognize(img_path), 0.5)

    def cancel_operation(self, instance):
        """取消操作"""
        self.reset_interface()

    def _calculate_coordinate_correction(self, ref_points):
        """坐标矫正"""
        self.correction_ready = False
        try:
            ref_voucher = ref_points.get("参考凭证", {})
            no_text = ref_points.get("No", {})
            receive_factory = ref_points.get("收货工厂", {})
            
            if not all([ref_voucher.get("x"), ref_voucher.get("y"), no_text.get("x"), no_text.get("y"), receive_factory.get("x"), receive_factory.get("y")]):
                return
            
            x1, y1 = ref_voucher["x"], ref_voucher["y"]
            x2, y2 = no_text["x"], no_text["y"]
            if x2 - x1 != 0:
                self.x_slope = (y2 - y1) / (x2 - x1)
                self.x_intercept = y1 - self.x_slope * x1
            else:
                self.x_slope = 0
                self.x_intercept = y1
            
            x3, y3 = receive_factory["x"], receive_factory["y"]
            if x3 - x1 != 0:
                self.y_slope = (y3 - y1) / (x3 - x1)
                self.y_intercept = y1 - self.y_slope * x1
            else:
                self.y_slope = float('inf')
                self.y_intercept = x1
            
            self.correction_ready = True
        except Exception as e:
            print(f"坐标矫正计算警告: {e}")

    def _correct_coordinate(self, x, y):
        """坐标矫正"""
        if not self.correction_ready:
            return x, y
        try:
            a1, b1, c1 = self.x_slope, -1, self.x_intercept
            corrected_y = abs(a1 * x + b1 * y + c1) / math.sqrt(a1**2 + b1**2)
            
            if self.y_slope == float('inf'):
                corrected_x = abs(x - self.y_intercept)
            else:
                a2, b2, c2 = self.y_slope, -1, self.y_intercept
                corrected_x = abs(a2 * x + b2 * y + c2) / math.sqrt(a2**2 + b2**2)
            
            return corrected_x, corrected_y
        except Exception as e:
            print(f"坐标矫正警告: {e}")
            return x, y

    def _init_ocr_client(self, force_recreate=False):
        """初始化OCR客户端"""
        if not TENCENT_SDK_AVAILABLE:
            raise Exception("腾讯云OCR SDK未安装或导入失败")
            
        try:
            need_recreate = force_recreate
            current_time = datetime.now()
            
            if not self.ocr_credential or not self.ocr_client:
                need_recreate = True
            elif self.ocr_credential_create_time and (current_time - self.ocr_credential_create_time) > timedelta(minutes=FIXED_CONFIG["ocr_expire_minutes"]):
                need_recreate = True
            
            if need_recreate:
                self.ocr_credential = credential.Credential(
                    WEWORK_CONFIG["ocr_secret_id"], 
                    WEWORK_CONFIG["ocr_secret_key"]
                )
                self.ocr_client = ocr_client.OcrClient(self.ocr_credential, "ap-shanghai")
                self.ocr_credential_create_time = current_time
                print("OCR客户端已重新初始化")
            
            return self.ocr_client
            
        except Exception as e:
            print(f"OCR客户端初始化失败: {e}")
            self.ocr_credential = None
            self.ocr_client = None
            self.ocr_credential_create_time = None
            raise

    def ocr_recognize(self, img_path, retry_count=0):
        """OCR识别"""
        if not TENCENT_SDK_AVAILABLE:
            self.show_dialog("腾讯云OCR SDK未安装，无法进行识别")
            return
            
        try:
            ocr_client = self._init_ocr_client()

            self.ocr_result = {
                "no": {"text":"", "x":0, "y":0, "corrected_x":0, "corrected_y":0},
                "name": {"text":"", "x":0, "y":0, "corrected_x":0, "corrected_y":0},
                "qty": {"text":"", "x":0, "y":0, "corrected_x":0, "corrected_y":0},
                "batch": {"text":"", "x":0, "y":0, "corrected_x":0, "corrected_y":0},
                "date": {"text":"", "x":0, "y":0, "corrected_x":0, "corrected_y":0}
            }

            try:
                with open(img_path, 'rb') as f:
                    image_data = f.read()
                    image_base64 = base64.b64encode(image_data).decode()
            except Exception as e:
                self.show_dialog(f"图片读取失败: {str(e)}")
                return

            req = models.GeneralBasicOCRRequest()
            req.ImageBase64 = image_base64
            req.IsWords = True
            resp = ocr_client.GeneralBasicOCR(req)

            all_texts = []
            ref_points = {
                "参考凭证": {"x": 0, "y": 0},
                "No": {"x": 0, "y": 0},
                "收货工厂": {"x": 0, "y": 0},
                "品名_表头": {"x": 0, "y": 0},
                "数量_表头": {"x": 0, "y": 0},
                "批次_表头": {"x": 0, "y": 0},
                "点收日期": {"x": 0, "y": 0}
            }

            for item in resp.TextDetections:
                text = item.DetectedText.strip()
                polygon = item.Polygon
                left_top_x = polygon[0].X
                left_top_y = polygon[0].Y
                center_x = (polygon[0].X + polygon[2].X) / 2
                center_y = (polygon[0].Y + polygon[2].Y) / 2
                
                all_texts.append({
                    "text": text,
                    "left_top_x": left_top_x,
                    "left_top_y": left_top_y,
                    "center_x": center_x,
                    "center_y": center_y
                })

                if "参考凭证" in text:
                    ref_points["参考凭证"]["x"] = left_top_x
                    ref_points["参考凭证"]["y"] = left_top_y
                elif any(k in text.upper() for k in ["N0", "NO", "NO."]):
                    ref_points["No"]["x"] = left_top_x
                    ref_points["No"]["y"] = left_top_y
                elif "收货工厂" in text:
                    ref_points["收货工厂"]["x"] = left_top_x
                    ref_points["收货工厂"]["y"] = left_top_y
                elif text in ["品名","晶名"] :
                    ref_points["品名_表头"]["x"] = center_x
                    ref_points["品名_表头"]["y"] = center_y
                elif text in ["数量", "数船"] :
                    ref_points["数量_表头"]["x"] = center_x
                    ref_points["数量_表头"]["y"] = center_y
                elif text in ["批次", "业次"]:
                    ref_points["批次_表头"]["x"] = center_x
                    ref_points["批次_表头"]["y"] = center_y
                elif "点收日期" in text:
                    ref_points["点收日期"]["x"] = center_x
                    ref_points["点收日期"]["y"] = center_y

            self._calculate_coordinate_correction(ref_points)
            ref_voucher_center = (ref_points["参考凭证"]["x"], ref_points["参考凭证"]["y"])
            corrected_ref_voucher = self._correct_coordinate(*ref_voucher_center)
            corrected_product_header = self._correct_coordinate(ref_points["品名_表头"]["x"], ref_points["品名_表头"]["y"])

            for item in all_texts:
                text = item["text"]
                center_x = item["center_x"]
                center_y = item["center_y"]
                corrected_x, corrected_y = self._correct_coordinate(center_x, center_y)
                
                if self.ocr_result["no"]["text"] == "":
                    if "参考凭证" in text or "NO." in text:
                        num_match = re.search(r'(\d{10})', text)
                        if num_match:
                            self.ocr_result["no"]["text"] = num_match.group(1)
                            self.ocr_result["no"]["x"] = center_x
                            self.ocr_result["no"]["y"] = center_y
                            self.ocr_result["no"]["corrected_x"] = corrected_x
                            self.ocr_result["no"]["corrected_y"] = corrected_y
                    elif re.match(r'^\d{10}$', text):
                        distance_to_x_line = abs(corrected_y - corrected_ref_voucher[1])
                        if distance_to_x_line < 30:
                            self.ocr_result["no"]["text"] = text
                            self.ocr_result["no"]["x"] = center_x
                            self.ocr_result["no"]["y"] = center_y
                            self.ocr_result["no"]["corrected_x"] = corrected_x
                            self.ocr_result["no"]["corrected_y"] = corrected_y

                if self.ocr_result["date"]["text"] == "" and (
                        re.match(r'^\d{4}\.\d{2}\.\d{2}$', text) or 
                        re.match(r'^\d{4},\d{2}\.\d{2}$', text) or 
                        re.match(r'^\d{4}.\d{2}\,\d{2}$', text) or 
                        re.match(r'^\d{4},\d{2}\,\d{2}$', text)
                    ):
                    if corrected_y > corrected_ref_voucher[1] + 20 and corrected_y < corrected_ref_voucher[1] + 80:
                        self.ocr_result["date"]["text"] = text
                        self.ocr_result["date"]["x"] = center_x
                        self.ocr_result["date"]["y"] = center_y
                        self.ocr_result["date"]["corrected_x"] = corrected_x
                        self.ocr_result["date"]["corrected_y"] = corrected_y

                if corrected_product_header[1] > 0:
                    if self.ocr_result["name"]["text"] == "" and re.match(r'^\d+$', text):
                        x_diff = abs(corrected_x - corrected_product_header[0])
                        y_diff = corrected_y - corrected_product_header[1]
                        if x_diff < 30 and y_diff > 10 and y_diff < 60:
                            self.ocr_result["name"]["text"] = text
                            self.ocr_result["name"]["x"] = center_x
                            self.ocr_result["name"]["y"] = center_y
                            self.ocr_result["name"]["corrected_x"] = corrected_x
                            self.ocr_result["name"]["corrected_y"] = corrected_y
                    
                    elif self.ocr_result["qty"]["text"] == "" and re.match(r'^\d+,\d+$', text):
                        corrected_qty_header = self._correct_coordinate(ref_points["数量_表头"]["x"], ref_points["数量_表头"]["y"])
                        x_diff = abs(corrected_x - corrected_qty_header[0])
                        y_diff = corrected_y - corrected_product_header[1]
                        if x_diff < 30 and y_diff > 10 and y_diff < 60:
                            self.ocr_result["qty"]["text"] = text
                            self.ocr_result["qty"]["x"] = center_x
                            self.ocr_result["qty"]["y"] = center_y
                            self.ocr_result["qty"]["corrected_x"] = corrected_x
                            self.ocr_result["qty"]["corrected_y"] = corrected_y
                    
                    elif self.ocr_result["batch"]["text"] == "" and re.match(r'^\d+$', text):
                        corrected_batch_header = self._correct_coordinate(ref_points["批次_表头"]["x"], ref_points["批次_表头"]["y"])
                        x_diff = abs(corrected_x - corrected_batch_header[0])
                        y_diff = corrected_y - corrected_product_header[1]
                        if x_diff < 30 and y_diff > 10 and y_diff < 60:
                            self.ocr_result["batch"]["text"] = text
                            self.ocr_result["batch"]["x"] = center_x
                            self.ocr_result["batch"]["y"] = center_y
                            self.ocr_result["batch"]["corrected_x"] = corrected_x
                            self.ocr_result["batch"]["corrected_y"] = corrected_y

            self._update_editable_labels()
            self.position_labels()

        except TencentCloudSDKException as err:
            error_msg = err.message if hasattr(err, 'message') else str(err)
            if any(keyword in error_msg for keyword in ["ExpiredToken", "InvalidCredential", "AuthFailure"]) and retry_count < FIXED_CONFIG["ocr_retry_times"]:
                print(f"OCR认证失效，正在重试（{retry_count+1}/{FIXED_CONFIG['ocr_retry_times']}）: {error_msg}")
                self._init_ocr_client(force_recreate=True)
                self.ocr_recognize(img_path, retry_count + 1)
            else:
                self.show_dialog(f"OCR识别错误: {error_msg}")
        except Exception as e:
            self.show_dialog(f"识别错误: {str(e)}")

    def _update_editable_labels(self):
        """更新标签内容"""
        self.no_label.update_content(self.ocr_result["no"]["text"])
        self.name_label.update_content(self.ocr_result["name"]["text"])
        self.qty_label.update_content(self.ocr_result["qty"]["text"])
        self.batch_label.update_content(self.ocr_result["batch"]["text"])
        self.date_label.update_content(self.ocr_result["date"]["text"])

    def position_labels(self):
        """标签定位"""
        img_widget = None
        for child in self.preview_layout.children:
            if isinstance(child, Image):
                img_widget = child
                break
        if not img_widget:
            return

        img_display_width = img_widget.width
        img_display_height = img_widget.height
        img_display_x = img_widget.x
        img_display_y = img_widget.y

        scale_x = img_display_width / self.img_width
        scale_y = img_display_height / self.img_height

        for key in ["no", "name", "qty", "batch", "date"]:
            label = getattr(self, f"{key}_label", None)
            if not label or not self.ocr_result[key]["text"]:
                continue
            use_x = self.ocr_result[key]["x"]
            use_y = self.ocr_result[key]["y"]
            label_x = img_display_x + use_x * scale_x - (label.width / 2)
            label_y = img_display_y + (self.img_height - use_y) * scale_y - 10
            # 新增：限制标签在屏幕内
            label_x = max(0, min(label_x, Window.width - label.width))
            label_y = max(0, min(label_y, Window.height - label.height))
            label.pos = (label_x, label_y)

    def submit_to_wework_table(self, instance):
        """提交到企微表格"""
        no_text = self.ocr_result["no"]["text"]
        if not no_text:
            self.show_dialog("点收单号不能为空!")
            return

        try:
            table_data = {}
            field_mapping = WEWORK_CONFIG["field_mapping"]
            
            table_data[field_mapping["no"]] = int(no_text) if no_text.isdigit() else no_text
            table_data[field_mapping["name"]] = self.ocr_result["name"]["text"]
            qty_text = self.ocr_result["qty"]["text"].replace(",", "")
            table_data[field_mapping["qty"]] = int(qty_text) if qty_text.isdigit() else qty_text
            table_data[field_mapping["batch"]] = self.ocr_result["batch"]["text"]
            
            date_text = self.ocr_result["date"]["text"].replace(",", ".").strip()
            if date_text:
                try:
                    date_obj = datetime.strptime(date_text, "%Y.%m.%d")
                    timestamp = int(date_obj.timestamp() * 1000)
                    table_data[field_mapping["date"]] = str(timestamp)
                except:
                    table_data[field_mapping["date"]] = date_text
            else:
                table_data[field_mapping["date"]] = ""

            request_body = {
                "add_records": [{"values": table_data}]
            }

            response = requests.post(
                url=WEWORK_CONFIG["webhook_url"],
                data=json.dumps(request_body, ensure_ascii=False),
                headers=FIXED_CONFIG["headers"],
                timeout=15
            )
            response.raise_for_status()  # 新增：抛出HTTP状态码异常
            result = response.json()
            if result.get("errcode") == FIXED_CONFIG["success_code"]:
                self.show_dialog(FIXED_CONFIG["success_msg"])
                self.reset_interface()
            else:
                err_msg = result.get("errmsg", "Unknown error")
                self.show_dialog(f"提交失败: {err_msg} (code: {result.get('errcode')})")

        except requests.exceptions.Timeout:
            self.show_dialog("请求超时，请检查网络")
        except requests.exceptions.ConnectionError:
            self.show_dialog("网络连接失败，请检查网络或Webhook地址")
        except Exception as e:
            self.show_dialog(f"提交错误: {str(e)}")

    def reset_interface(self):
        """重置界面"""
        try:
            if self.preview_layout:
                for child in self.preview_layout.children[:]:
                    self.preview_layout.remove_widget(child)
                self.root.remove_widget(self.preview_layout)
                self.preview_layout = None
            self.root.ids.btn_container.opacity = 1
            self.ocr_result = {
                "no": {"text":"", "x":0, "y":0, "corrected_x":0, "corrected_y":0},
                "name": {"text":"", "x":0, "y":0, "corrected_x":0, "corrected_y":0},
                "qty": {"text":"", "x":0, "y":0, "corrected_x":0, "corrected_y":0},
                "batch": {"text":"", "x":0, "y":0, "corrected_x":0, "corrected_y":0},
                "date": {"text":"", "x":0, "y":0, "corrected_x":0, "corrected_y":0}
            }
            self.correction_ready = False
        except Exception as e:
            print(f"界面重置警告: {e}")

    # ====================== 核心修改：最简单的基础弹窗（中文显示） ======================
    def show_dialog(self, msg):
        """
        最简单的基础弹窗，确保中文显示
        :param msg: 要显示的中文信息
        """
        # 1. 创建弹窗内容布局（仅包含标签+关闭按钮）
        content_layout = BoxLayout(orientation='vertical', spacing=10, padding=20)
        
        # 2. 创建显示中文的标签（指定中文字体）
        msg_label = Label(
            text=msg,
            font_name='Chinese',  # 确保用已注册的中文字体
            font_size=18,
            halign='center',
            valign='middle'
        )
        
        # 3. 创建关闭按钮（指定中文字体）
        close_btn = MDFillRoundFlatButton(
            text="确定",
            font_name='Chinese',
            font_size=16,
            size_hint=(1, None),
            height=40
        )
        
        # 4. 添加控件到布局
        content_layout.add_widget(msg_label)
        content_layout.add_widget(close_btn)
        
        # 5. 创建原生基础弹窗
        self.popup = Popup(
            title="提示",          # 弹窗标题（中文）
            content=content_layout,
            size_hint=(0.8, 0.4),  # 弹窗尺寸（相对屏幕）
            auto_dismiss=False     # 禁止点击外部关闭，必须点按钮
        )
        
        # 6. 绑定按钮关闭弹窗
        close_btn.bind(on_press=self.popup.dismiss)
        
        # 7. 显示弹窗
        self.popup.open()

    def open_settings_dialog(self):
        """打开设置对话框"""
        try:
            settings_content = Builder.load_string(SETTINGS_DIALOG_KV)
            
            # 填充配置
            settings_content.ids.ocr_secret_id.text = WEWORK_CONFIG["ocr_secret_id"]
            settings_content.ids.ocr_secret_key.text = WEWORK_CONFIG["ocr_secret_key"]
            settings_content.ids.webhook_url.text = WEWORK_CONFIG["webhook_url"]
            settings_content.ids.field_mapping.text = json.dumps(WEWORK_CONFIG["field_mapping"], ensure_ascii=False, indent=2)
            
            # 绑定按钮事件
            settings_content.ids.save_btn.bind(on_press=lambda x: self.save_settings(settings_content))
            settings_content.ids.cancel_btn.bind(on_press=lambda x: self.close_settings_dialog())
            
            # 创建设置对话框
            self.settings_dialog = MDDialog(
                title="系统配置",
                type="custom",
                content_cls=settings_content,
                size_hint=(0.95, 0.8),
                pos_hint={"top": 1},
                auto_dismiss=False
            )
            self.settings_dialog.open()
        except Exception as e:
            self.show_dialog(f"打开设置失败: {str(e)}")

    def save_settings(self, settings_layout):
        """保存设置"""
        global WEWORK_CONFIG
        
        try:
            new_config = {
                "ocr_secret_id": settings_layout.ids.ocr_secret_id.text.strip(),
                "ocr_secret_key": settings_layout.ids.ocr_secret_key.text.strip(),
                "webhook_url": settings_layout.ids.webhook_url.text.strip()
            }
            
            # 解析JSON
            try:
                field_mapping_text = settings_layout.ids.field_mapping.text.strip()
                if field_mapping_text:
                    new_config["field_mapping"] = json.loads(field_mapping_text)
                else:
                    new_config["field_mapping"] = WEWORK_CONFIG["field_mapping"]
            except json.JSONDecodeError:
                self.show_dialog("字段映射格式错误，请输入有效的JSON格式")
                return
            
            # 验证必填项
            if not new_config["ocr_secret_id"] or not new_config["ocr_secret_key"] or not new_config["webhook_url"]:
                self.show_dialog("Secret ID、Secret Key、Webhook URL不能为空")
                return
            
            # 保存配置
            if save_config(new_config):
                WEWORK_CONFIG = new_config
                self.ocr_client = None
                self.ocr_credential = None
                self.ocr_credential_create_time = None
                self.show_dialog("配置保存成功！")
                self.close_settings_dialog()
            else:
                self.show_dialog("配置保存失败，请检查权限")
        except Exception as e:
            self.show_dialog(f"保存配置失败: {str(e)}")

    def close_settings_dialog(self):
        """关闭设置对话框"""
        if self.settings_dialog:
            self.settings_dialog.dismiss()
            self.settings_dialog = None

if __name__ == "__main__":
    try:
        ReceiptApp().run()
    except Exception as e:
        print(f"应用启动异常: {e}")
        if platform == 'android' and 'app_storage_path' in locals():
            with open(os.path.join(app_storage_path(), 'app_error.log'), 'w') as f:
                f.write(str(e))