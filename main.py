import base64
import requests
import os
import re
import math
import json
import threading
import shutil
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
from kivy.metrics import dp, sp
from kivy.config import Config
from kivy.app import App
# 导入Kivy原生基础弹窗（核心）
from kivy.uix.popup import Popup
import sys
Config.set('kivy', 'log_level', 'error')  # 减少日志输出

# ====================== 强制中文字体配置（确保弹窗中文显示） ======================
from kivy.core.text import LabelBase
def register_chinese_fonts():
    """注册中文字体，兼容 Windows / Android（含 vivo、OPPO、小米等各厂商路径）"""
    import glob as _glob

    if platform == 'win':
        candidates = [
            'C:/Windows/Fonts/msyh.ttc',
            'C:/Windows/Fonts/simhei.ttf',
            'C:/Windows/Fonts/simsun.ttc',
        ]
    elif platform == 'android':
        # 常见固定路径（覆盖 Android 5–14 及主流厂商）
        candidates = [
            '/system/fonts/NotoSansCJK-Regular.ttc',
            '/system/fonts/NotoSansCJKsc-Regular.otf',
            '/system/fonts/NotoSansSC-Regular.otf',
            '/system/fonts/NotoSerifCJK-Regular.ttc',
            '/system/fonts/DroidSansFallback.ttf',
            '/system/fonts/DroidSansFallbackFull.ttf',
            '/system/fonts/SourceHanSansCN-Regular.otf',
            '/system/fonts/MTLmr3m.ttf',
        ]
        # 通配符兜底：扫描系统字体目录里含 CJK/SC/CN/Chinese 的文件
        for pattern in [
            '/system/fonts/*CJK*.ttc',
            '/system/fonts/*CJK*.otf',
            '/system/fonts/*SC*.otf',
            '/system/fonts/*CN*.ttf',
            '/system/fonts/*chinese*.ttf',
            '/system/fonts/*Chinese*.ttf',
        ]:
            candidates += _glob.glob(pattern)
    else:
        candidates = []

    for font_path in candidates:
        if os.path.exists(font_path):
            try:
                LabelBase.register(name='Chinese', fn_regular=font_path)
                Config.set('kivy', 'default_font', ['Chinese', font_path])
                print(f"成功加载中文字体: {font_path}")
                return
            except Exception as e:
                print(f"字体加载失败({font_path}): {e}")
                continue

    # 全部失败时 fallback（乱码但不崩溃）
    LabelBase.register(name='Chinese', fn_regular='Roboto')
    Config.set('kivy', 'default_font', ['Chinese', 'Roboto'])
    print("警告: 未找到中文字体，使用 Roboto 替代（中文可能显示为方框）")

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

    # 右上角设置按钮（纯文字，兼容所有 Android 字体）
    Button:
        text: "设置"
        font_name: 'Chinese'
        font_size: sp(18)
        pos_hint: {"right": 0.99, "top": 0.99}
        size_hint: None, None
        size: dp(80), dp(48)
        background_normal: ""
        background_color: (0.2, 0.2, 0.2, 0.7)
        color: (1, 1, 1, 1)
        on_press: app.open_settings_dialog()
    
    # 按钮容器
    MDBoxLayout:
        id: btn_container
        orientation: 'horizontal'
        size_hint: 1, None
        height: dp(72)
        pos_hint: {'center_x': 0.5, 'y': 0.04}
        spacing: dp(16)
        padding: [dp(20), 0, dp(20), 0]
        
        MDFillRoundFlatButton:
            text: "拍照"
            size_hint_y: None
            height: dp(72)
            md_bg_color: "#4CAF50"
            font_size: sp(22)
            font_name: 'Chinese'
            on_press: app.take_photo()
        
        MDFillRoundFlatButton:
            text: "选择照片"
            size_hint_y: None
            height: dp(72)
            md_bg_color: "#2196F3"
            font_size: sp(22)
            font_name: 'Chinese'
            on_press: app.choose_image()
        
        MDFillRoundFlatButton:
            text: "退出"
            size_hint_y: None
            height: dp(72)
            md_bg_color: "#F44336"
            font_size: sp(22)
            font_name: 'Chinese'
            on_press: app.exit_app()
'''

# ====================== 设置对话框布局（纯原生 Kivy，避免 MDDialog 在 Android 段错误） ======================
# 不再使用 SETTINGS_DIALOG_KV，改为在代码里动态创建控件

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
        if platform == 'android':
            if not check_permission(Permission.CAMERA):
                self.show_dialog("请先授予相机权限")
                self._request_permissions_safe()
                return
            try:
                self._android_take_photo()
            except Exception as e:
                self.show_dialog(f"相机调用失败: {str(e)}")
        else:
            # PC 端用 plyer
            self.current_img_path = self.get_safe_image_path()
            try:
                from plyer import camera
                Clock.schedule_once(lambda x: camera.take_picture(
                    filename=self.current_img_path,
                    on_complete=self.on_image_selected
                ), 0.1)
            except Exception as e:
                self.show_dialog(f"相机调用失败: {str(e)}")

    def _android_take_photo(self):
        """
        Android 拍照实现（规避 FileUriExposedException）：
        用 MediaStore 创建 content:// URI 作为相机输出目标，
        通过 startActivityForResult + on_activity_result 获取结果，
        无需 FileProvider XML 配置。
        """
        from jnius import autoclass, cast
        from android import mActivity
        from android.activity import bind as activity_bind

        # 只加载必要的 Java 类，避免从接口/父类继承链取常量不稳定的问题
        Intent        = autoclass('android.content.Intent')
        MediaStore    = autoclass('android.provider.MediaStore')
        ImgMedia      = autoclass('android.provider.MediaStore$Images$Media')
        ContentValues = autoclass('android.content.ContentValues')
        Context       = autoclass('android.content.Context')

        context = cast(Context, mActivity.getApplicationContext())

        # 用毫秒时间戳生成唯一文件名，避免重复插入同名记录触发 SQLite UNIQUE 约束错误
        import time as _time
        unique_name = 'receipt_{}.jpg'.format(int(_time.time() * 1000))

        # 在 MediaStore 中插入一条待写入的图片记录，取得 content:// URI
        # 列名直接用字符串字面量，规避 jnius 经接口/父类取静态字段类型不稳定的问题
        values = ContentValues()
        values.put('_display_name', unique_name)
        values.put('mime_type', 'image/jpeg')
        self._camera_output_uri = context.getContentResolver().insert(
            ImgMedia.EXTERNAL_CONTENT_URI, values
        )
        if self._camera_output_uri is None:
            raise RuntimeError("无法创建 MediaStore 图片 URI，请检查存储权限")

        # 启动系统相机，指定输出到 content:// URI（避免 FileUriExposedException）
        intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
        # 显式 cast 为 Parcelable，帮助 jnius 解析 putExtra(String, Parcelable) 重载
        intent.putExtra(
            MediaStore.EXTRA_OUTPUT,
            cast('android.os.Parcelable', self._camera_output_uri)
        )

        REQUEST_CAMERA = 0x2001
        # 保存 context 引用供结果回调使用
        _context = context
        _uri = self._camera_output_uri

        def on_result(request_code, result_code, data):
            if request_code != REQUEST_CAMERA:
                return
            from android.activity import unbind as activity_unbind
            activity_unbind(on_activity_result=on_result)

            RESULT_OK = -1  # android.app.Activity.RESULT_OK
            if result_code == RESULT_OK:
                uri_str = _uri.toString()
                # 后台处理图片；处理完成后由 _prepare_image_bg 自行清理 MediaStore 记录
                self._camera_mediastore_uri  = _uri
                self._camera_mediastore_ctx  = _context
                threading.Thread(
                    target=self._prepare_image_bg,
                    args=(uri_str,),
                    daemon=True
                ).start()
            else:
                # 用户取消拍照：删除刚才创建的空 MediaStore 记录，避免残留
                try:
                    _context.getContentResolver().delete(_uri, None, None)
                except Exception:
                    pass

        activity_bind(on_activity_result=on_result)
        mActivity.startActivityForResult(intent, REQUEST_CAMERA)

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

    def _copy_to_local(self, src_path):
        """
        Android Scoped Storage 兼容：将外部选取的图片复制到 App 私有目录。
        App 私有目录无需存储权限，PIL/Kivy Image 均可直接读取。
        """
        try:
            local_path = self.get_safe_image_path()
            shutil.copy(src_path, local_path)
            return local_path
        except Exception as e:
            print(f"[copy_to_local] 复制失败({src_path}): {e}")
            return src_path  # 回退到原路径，仍可能失败但已尽力

    def on_file_selected(self, selection):
        """plyer 回调（Android 上可能在非主线程调用），统一转后台线程处理"""
        if not (selection and len(selection) > 0):
            return
        src_path = selection[0]
        threading.Thread(
            target=self._prepare_image_bg, args=(src_path,), daemon=True
        ).start()

    def _get_display_image_path(self):
        """获取用于 Kivy 显示的独立图片路径（与 OCR 路径分开）"""
        ocr_path = self.get_safe_image_path()
        return ocr_path.replace('receipt_ocr.jpg', 'receipt_display.jpg')

    # ------------------------------------------------------------------
    # Android 原生图片处理（BitmapFactory + ContentResolver）
    # 支持 content URI、HEIC、AVIF、WebP 等 PIL 无法处理的情况
    # ------------------------------------------------------------------
    def _android_process_image(self, src_path, ocr_path, display_path, max_dim=1920):
        """
        Android 专用：用 Java BitmapFactory / ContentResolver 读取任意格式图片，
        输出：
          ocr_path     - 原始画质 JPEG（供腾讯 OCR API）
          display_path - 缩放至 max_dim 的 JPEG（供 Kivy Image 显示）
        返回 (img_w, img_h) 为 display 图片的实际尺寸
        """
        from jnius import autoclass, cast
        from android import mActivity

        Context        = autoclass('android.content.Context')
        Uri            = autoclass('android.net.Uri')
        BitmapFactory  = autoclass('android.graphics.BitmapFactory')
        BitmapOpts     = autoclass('android.graphics.BitmapFactory$Options')
        CompressFormat = autoclass('android.graphics.Bitmap$CompressFormat')
        FileOutputStream = autoclass('java.io.FileOutputStream')

        context = cast(Context, mActivity.getApplicationContext())
        is_content_uri = src_path.startswith('content://')

        def open_stream():
            if is_content_uri:
                return context.getContentResolver().openInputStream(
                    Uri.parse(src_path)
                )
            return None  # 普通文件路径用 decodeFile

        # ---- Step 1: 获取原始尺寸（不加载像素）----
        opts_bounds = BitmapOpts()
        opts_bounds.inJustDecodeBounds = True
        if is_content_uri:
            s = open_stream()
            BitmapFactory.decodeStream(s, None, opts_bounds)
            s.close()
        else:
            BitmapFactory.decodeFile(src_path, opts_bounds)
        orig_w, orig_h = opts_bounds.outWidth, opts_bounds.outHeight
        if orig_w <= 0 or orig_h <= 0:
            raise ValueError(f"BitmapFactory 无法解码图片尺寸: {src_path}")

        # ---- Step 2: 保存 OCR 原图（保持原始质量）----
        opts_full = BitmapOpts()
        opts_full.inSampleSize = 1
        if is_content_uri:
            s = open_stream()
            bmp_full = BitmapFactory.decodeStream(s, None, opts_full)
            s.close()
        else:
            bmp_full = BitmapFactory.decodeFile(src_path, opts_full)
        if bmp_full is None:
            raise ValueError("BitmapFactory 解码返回 null（原图）")
        fos = FileOutputStream(ocr_path)
        bmp_full.compress(CompressFormat.JPEG, 95, fos)
        fos.flush(); fos.close()
        bmp_full.recycle()

        # ---- Step 3: 保存缩放 display 图（供 Kivy 显示）----
        sample = 1
        while orig_w // sample > max_dim or orig_h // sample > max_dim:
            sample *= 2
        opts_disp = BitmapOpts()
        opts_disp.inSampleSize = sample
        if is_content_uri:
            s = open_stream()
            bmp_disp = BitmapFactory.decodeStream(s, None, opts_disp)
            s.close()
        else:
            bmp_disp = BitmapFactory.decodeFile(src_path, opts_disp)
        if bmp_disp is None:
            raise ValueError("BitmapFactory 解码返回 null（display）")
        fos2 = FileOutputStream(display_path)
        bmp_disp.compress(CompressFormat.JPEG, 90, fos2)
        fos2.flush(); fos2.close()
        disp_w = bmp_disp.getWidth()
        disp_h = bmp_disp.getHeight()
        bmp_disp.recycle()

        return disp_w, disp_h

    def _prepare_image_bg(self, src_path):
        """
        后台线程：
        - Android：用 BitmapFactory + ContentResolver 处理（支持所有格式 + content URI）
        - PC：用 PIL 处理
        ocr_path     → 原图（供腾讯 OCR API 识别）
        display_path → 缩放 JPEG（供 Kivy Image 控件显示）
        """
        try:
            ocr_path     = self.get_safe_image_path()
            display_path = self._get_display_image_path()
            img_w, img_h = 0, 0

            if platform == 'android':
                # Android：原生 BitmapFactory 处理（兼容 content URI / HEIC / WebP 等）
                try:
                    img_w, img_h = self._android_process_image(
                        src_path, ocr_path, display_path
                    )
                except Exception as e:
                    print(f"[Android BitmapFactory 失败] {e}")
                    # 最后兜底：用 shutil 复制，display 回退到 ocr_path
                    try:
                        shutil.copy(src_path, ocr_path)
                    except Exception:
                        pass
                    display_path = ocr_path
            else:
                # PC：PIL 处理
                try:
                    from PIL import Image as PILImage, ImageOps
                    pil_img = PILImage.open(src_path)
                    try:
                        pil_img = ImageOps.exif_transpose(pil_img)
                    except Exception:
                        pass
                    if pil_img.mode != 'RGB':
                        pil_img = pil_img.convert('RGB')
                    # 原图存 ocr_path
                    pil_img.save(ocr_path, 'JPEG', quality=95)
                    # 缩放版存 display_path
                    img_w, img_h = pil_img.size
                    MAX_DIM = 1920
                    if img_w > MAX_DIM or img_h > MAX_DIM:
                        scale = MAX_DIM / max(img_w, img_h)
                        img_w = int(img_w * scale)
                        img_h = int(img_h * scale)
                        pil_img = pil_img.resize((img_w, img_h), PILImage.LANCZOS)
                    pil_img.save(display_path, 'JPEG', quality=90)
                    pil_img.close()
                except Exception as e:
                    print(f"[PIL 处理失败] {e}")
                    shutil.copy(src_path, ocr_path)
                    display_path = ocr_path

            if not os.path.exists(ocr_path):
                Clock.schedule_once(
                    lambda dt: self.show_dialog("图片文件不存在，请重新选择"), 0
                )
                return

            # 拍照流程：图片已复制到私有目录，删除 MediaStore 中的临时记录
            # 避免相册中积累无用的临时照片，且消除下次 insert 的 UNIQUE 冲突风险
            if platform == 'android':
                try:
                    ms_uri = getattr(self, '_camera_mediastore_uri', None)
                    ms_ctx = getattr(self, '_camera_mediastore_ctx', None)
                    if ms_uri is not None and ms_ctx is not None:
                        ms_ctx.getContentResolver().delete(ms_uri, None, None)
                        self._camera_mediastore_uri = None
                        self._camera_mediastore_ctx = None
                except Exception as del_e:
                    print(f"[MediaStore 清理失败] {del_e}")

            Clock.schedule_once(
                lambda dt: self._start_preview(display_path, ocr_path, img_w, img_h), 0
            )
        except Exception as e:
            Clock.schedule_once(
                lambda dt, msg=str(e): self.show_dialog(f"图片准备失败: {msg}"), 0
            )

    def _start_preview(self, display_path, ocr_path, img_w, img_h):
        """主线程：隐藏主界面按钮，延迟一帧后建预览 UI"""
        self.current_img_path = ocr_path    # OCR 始终用原图
        self.img_width = img_w
        self.img_height = img_h
        self.root.ids.btn_container.opacity = 0
        # 延迟一帧让按钮隐藏完成后再建 UI，避免布局抖动
        Clock.schedule_once(
            lambda dt: self._load_preview_layout(display_path, ocr_path), 0.05
        )

    def on_image_selected(self, img_path):
        """拍照回调（plyer camera，已在主线程）"""
        if not os.path.exists(img_path):
            self.show_dialog("图片文件不存在")
            return
        # 拍照的图片同样需要预处理，走后台线程
        threading.Thread(
            target=self._prepare_image_bg, args=(img_path,), daemon=True
        ).start()

    def _load_preview_layout(self, display_path, ocr_path=None):
        """
        主线程：建预览 UI
        display_path - PIL 处理后的图片，供 Kivy Image 显示
        ocr_path     - 原始图片，供腾讯 OCR API 使用（若为 None 则与 display_path 相同）
        """
        if ocr_path is None:
            ocr_path = display_path
        self.preview_layout = FloatLayout(size_hint=(1, 1))

        # 图片控件（nocache=True 防止 Kivy 复用旧纹理缓存）
        img_widget = Image(
            source=display_path,
            size_hint=(0.9, 0.7),
            pos_hint={'center_x': 0.5, 'center_y': 0.58},
            allow_stretch=True,
            keep_ratio=True,
            nocache=True,
        )
        # 若 PIL 未能获取尺寸，等 Image 控件纹理加载后再定位标签
        if self.img_width == 0 or self.img_height == 0:
            def _on_texture(inst, texture):
                if texture:
                    self.img_width, self.img_height = texture.width, texture.height
                    Clock.schedule_once(lambda dt: self.position_labels(), 0.1)
            img_widget.bind(texture=_on_texture)
        self.preview_layout.add_widget(img_widget)

        # 可编辑识别结果标签（dp 单位，适配高 DPI 手机屏幕）
        lbl_size = (dp(220), dp(34))
        lbl_fs   = sp(15)
        self.no_label    = EditableLabel(prefix="单号: ",  key="no",    size_hint=(None,None), size=lbl_size, color=(1,0,0,1), font_size=lbl_fs, bold=True)
        self.name_label  = EditableLabel(prefix="品名: ",  key="name",  size_hint=(None,None), size=lbl_size, color=(1,0,0,1), font_size=lbl_fs, bold=True)
        self.qty_label   = EditableLabel(prefix="数量: ",  key="qty",   size_hint=(None,None), size=lbl_size, color=(1,0,0,1), font_size=lbl_fs, bold=True)
        self.batch_label = EditableLabel(prefix="批次: ",  key="batch", size_hint=(None,None), size=lbl_size, color=(1,0,0,1), font_size=lbl_fs, bold=True)
        self.date_label  = EditableLabel(prefix="日期: ",  key="date",  size_hint=(None,None), size=lbl_size, color=(1,0,0,1), font_size=lbl_fs, bold=True)
        for lbl in [self.no_label, self.name_label, self.qty_label, self.batch_label, self.date_label]:
            lbl.app = self
            self.preview_layout.add_widget(lbl)

        # 提交 / 取消按钮
        btn_box = BoxLayout(
            size_hint=(0.92, None), height=dp(64),
            pos_hint={'center_x': 0.5, 'y': 0.03}, spacing=dp(10)
        )
        self.submit_btn = MDFillRoundFlatButton(
            text="提交到企微表格",
            size_hint=(0.7, 1),
            md_bg_color="#FF9800",
            font_size=sp(20),
            font_name='Chinese',
            on_press=self.submit_to_wework_table,
        )
        self.cancel_btn = MDFillRoundFlatButton(
            text="取消",
            size_hint=(0.3, 1),
            md_bg_color="#F44336",
            font_size=sp(18),
            font_name='Chinese',
            on_press=self.cancel_operation,
        )
        btn_box.add_widget(self.submit_btn)
        btn_box.add_widget(self.cancel_btn)
        self.preview_layout.add_widget(btn_box)

        self.root.add_widget(self.preview_layout)

        # OCR 使用原始图片路径（非 PIL 处理版），避免二次编码影响识别
        Clock.schedule_once(lambda dt: self.ocr_recognize(ocr_path), 0.3)

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
        """OCR识别 —— 在后台线程执行网络请求，避免主线程阻塞导致白屏"""
        if not TENCENT_SDK_AVAILABLE:
            self.show_dialog("腾讯云OCR SDK未安装，无法进行识别")
            return

        def _run():
            try:
                ocr_client = self._init_ocr_client()

                result = {
                    "no":    {"text":"", "x":0, "y":0, "corrected_x":0, "corrected_y":0},
                    "name":  {"text":"", "x":0, "y":0, "corrected_x":0, "corrected_y":0},
                    "qty":   {"text":"", "x":0, "y":0, "corrected_x":0, "corrected_y":0},
                    "batch": {"text":"", "x":0, "y":0, "corrected_x":0, "corrected_y":0},
                    "date":  {"text":"", "x":0, "y":0, "corrected_x":0, "corrected_y":0},
                }

                try:
                    with open(img_path, 'rb') as f:
                        image_base64 = base64.b64encode(f.read()).decode()
                except Exception as e:
                    Clock.schedule_once(lambda dt, msg=str(e): self.show_dialog(f"图片读取失败: {msg}"), 0)
                    return

                req = models.GeneralBasicOCRRequest()
                req.ImageBase64 = image_base64
                req.IsWords = True
                resp = ocr_client.GeneralBasicOCR(req)

                all_texts = []
                ref_points = {
                    "参考凭证": {"x": 0, "y": 0},
                    "No":      {"x": 0, "y": 0},
                    "收货工厂":  {"x": 0, "y": 0},
                    "品名_表头": {"x": 0, "y": 0},
                    "数量_表头": {"x": 0, "y": 0},
                    "批次_表头": {"x": 0, "y": 0},
                    "点收日期":  {"x": 0, "y": 0},
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
                        "center_y": center_y,
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
                    elif text in ["品名", "晶名"]:
                        ref_points["品名_表头"]["x"] = center_x
                        ref_points["品名_表头"]["y"] = center_y
                    elif text in ["数量", "数船"]:
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
                corrected_product_header = self._correct_coordinate(
                    ref_points["品名_表头"]["x"], ref_points["品名_表头"]["y"]
                )

                for item in all_texts:
                    text = item["text"]
                    center_x = item["center_x"]
                    center_y = item["center_y"]
                    corrected_x, corrected_y = self._correct_coordinate(center_x, center_y)

                    if result["no"]["text"] == "":
                        if "参考凭证" in text or "NO." in text:
                            num_match = re.search(r'(\d{10})', text)
                            if num_match:
                                result["no"].update({"text": num_match.group(1), "x": center_x, "y": center_y,
                                                     "corrected_x": corrected_x, "corrected_y": corrected_y})
                        elif re.match(r'^\d{10}$', text):
                            if abs(corrected_y - corrected_ref_voucher[1]) < 30:
                                result["no"].update({"text": text, "x": center_x, "y": center_y,
                                                     "corrected_x": corrected_x, "corrected_y": corrected_y})

                    if result["date"]["text"] == "" and (
                        re.match(r'^\d{4}\.\d{2}\.\d{2}$', text) or
                        re.match(r'^\d{4},\d{2}\.\d{2}$', text) or
                        re.match(r'^\d{4}.\d{2}\,\d{2}$', text) or
                        re.match(r'^\d{4},\d{2}\,\d{2}$', text)
                    ):
                        if corrected_ref_voucher[1] + 20 < corrected_y < corrected_ref_voucher[1] + 80:
                            result["date"].update({"text": text, "x": center_x, "y": center_y,
                                                   "corrected_x": corrected_x, "corrected_y": corrected_y})

                    if corrected_product_header[1] > 0:
                        if result["name"]["text"] == "" and re.match(r'^\d+$', text):
                            x_diff = abs(corrected_x - corrected_product_header[0])
                            y_diff = corrected_y - corrected_product_header[1]
                            if x_diff < 30 and 10 < y_diff < 60:
                                result["name"].update({"text": text, "x": center_x, "y": center_y,
                                                       "corrected_x": corrected_x, "corrected_y": corrected_y})
                        elif result["qty"]["text"] == "" and re.match(r'^\d+,\d+$', text):
                            corrected_qty_header = self._correct_coordinate(
                                ref_points["数量_表头"]["x"], ref_points["数量_表头"]["y"]
                            )
                            x_diff = abs(corrected_x - corrected_qty_header[0])
                            y_diff = corrected_y - corrected_product_header[1]
                            if x_diff < 30 and 10 < y_diff < 60:
                                result["qty"].update({"text": text, "x": center_x, "y": center_y,
                                                      "corrected_x": corrected_x, "corrected_y": corrected_y})
                        elif result["batch"]["text"] == "" and re.match(r'^\d+$', text):
                            corrected_batch_header = self._correct_coordinate(
                                ref_points["批次_表头"]["x"], ref_points["批次_表头"]["y"]
                            )
                            x_diff = abs(corrected_x - corrected_batch_header[0])
                            y_diff = corrected_y - corrected_product_header[1]
                            if x_diff < 30 and 10 < y_diff < 60:
                                result["batch"].update({"text": text, "x": center_x, "y": center_y,
                                                        "corrected_x": corrected_x, "corrected_y": corrected_y})

                # 回主线程更新 UI
                def _apply(dt):
                    self.ocr_result = result
                    self._update_editable_labels()
                    # 等图片控件完成布局后再定位标签
                    Clock.schedule_once(lambda dt2: self.position_labels(), 0.2)
                Clock.schedule_once(_apply, 0)

            except TencentCloudSDKException as err:
                error_msg = err.message if hasattr(err, 'message') else str(err)
                if any(k in error_msg for k in ["ExpiredToken", "InvalidCredential", "AuthFailure"]) \
                        and retry_count < FIXED_CONFIG["ocr_retry_times"]:
                    print(f"OCR认证失效，重试({retry_count+1}): {error_msg}")
                    self._init_ocr_client(force_recreate=True)
                    Clock.schedule_once(lambda dt: self.ocr_recognize(img_path, retry_count + 1), 0)
                else:
                    Clock.schedule_once(lambda dt, msg=error_msg: self.show_dialog(f"OCR识别错误: {msg}"), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt, msg=str(e): self.show_dialog(f"识别错误: {msg}"), 0)

        threading.Thread(target=_run, daemon=True).start()

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
        content_layout = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(20))
        
        # 2. 创建显示中文的标签（指定中文字体）
        msg_label = Label(
            text=msg,
            font_name='Chinese',
            font_size=sp(22),
            halign='center',
            valign='middle'
        )
        msg_label.bind(size=lambda inst, val: setattr(inst, 'text_size', val))

        # 3. 创建关闭按钮（指定中文字体）
        close_btn = MDFillRoundFlatButton(
            text="确定",
            font_name='Chinese',
            font_size=sp(20),
            size_hint=(1, None),
            height=dp(52)
        )
        
        # 4. 添加控件到布局
        content_layout.add_widget(msg_label)
        content_layout.add_widget(close_btn)
        
        # 5. 创建原生基础弹窗
        self.popup = Popup(
            title="提示",
            title_font='Chinese',
            title_size=sp(20),
            content=content_layout,
            size_hint=(0.85, 0.42),
            auto_dismiss=False
        )
        
        # 6. 绑定按钮关闭弹窗
        close_btn.bind(on_press=self.popup.dismiss)
        
        # 7. 显示弹窗
        self.popup.open()

    def open_settings_dialog(self):
        """打开设置对话框（纯原生 Popup，字号和控件均适配手机屏幕）"""
        try:
            from kivy.uix.scrollview import ScrollView
            from kivy.uix.button import Button

            # ---- 标签 ----
            def make_label(text):
                return Label(
                    text=text,
                    font_name='Chinese',
                    font_size=sp(18),
                    size_hint_y=None,
                    height=dp(38),
                    color=(0.15, 0.15, 0.15, 1),
                    halign='left',
                    valign='middle',
                    text_size=(Window.width * 0.85, None),
                )

            # ---- 输入框 ----
            def make_input(hint, text='', multiline=False, height=None):
                return TextInput(
                    hint_text=hint,
                    text=text,
                    font_name='Chinese',
                    font_size=sp(17),
                    multiline=multiline,
                    size_hint_y=None,
                    height=height if height is not None else dp(58),
                    padding=[dp(12), dp(10), dp(12), dp(10)],
                    background_color=(0.97, 0.97, 0.97, 1),
                    foreground_color=(0, 0, 0, 1),
                    cursor_color=(0.2, 0.5, 1, 1),
                )

            self._set_ocr_id  = make_input('请输入 OCR Secret ID',  WEWORK_CONFIG.get('ocr_secret_id', ''))
            self._set_ocr_key = make_input('请输入 OCR Secret Key', WEWORK_CONFIG.get('ocr_secret_key', ''))
            self._set_webhook = make_input('请输入企微 Webhook URL', WEWORK_CONFIG.get('webhook_url', ''))
            self._set_mapping = make_input(
                '字段映射 JSON',
                json.dumps(WEWORK_CONFIG.get('field_mapping', {}), ensure_ascii=False, indent=2),
                multiline=True,
                height=dp(160),
            )

            # ---- 按钮 ----
            def make_btn(text, bg):
                return Button(
                    text=text,
                    font_name='Chinese',
                    font_size=sp(20),
                    bold=True,
                    background_normal='',
                    background_color=bg,
                    color=(1, 1, 1, 1),
                    size_hint=(0.46, 1),
                )

            save_btn   = make_btn('保存', (0.18, 0.65, 0.18, 1))
            cancel_btn = make_btn('取消', (0.85, 0.18, 0.18, 1))

            btn_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(64), spacing=dp(16))
            btn_row.add_widget(save_btn)
            btn_row.add_widget(cancel_btn)

            # ---- 标题 ----
            title_lbl = Label(
                text='系统配置',
                font_name='Chinese',
                font_size=sp(24),
                bold=True,
                size_hint_y=None,
                height=dp(56),
                color=(0.1, 0.1, 0.1, 1),
            )

            # ---- 分隔线（用 BoxLayout 模拟） ----
            def divider():
                b = BoxLayout(size_hint_y=None, height=dp(2))
                b.canvas.before.add(__import__('kivy.graphics', fromlist=['Color']).Color(0.8, 0.8, 0.8, 1))
                b.canvas.before.add(__import__('kivy.graphics', fromlist=['Rectangle']).Rectangle(pos=b.pos, size=b.size))
                return b

            # ---- 整体内容 ----
            inner = BoxLayout(
                orientation='vertical',
                spacing=dp(10),
                padding=[dp(18), dp(12), dp(18), dp(18)],
                size_hint_y=None,
            )
            items = [
                title_lbl,
                make_label('OCR Secret ID'),   self._set_ocr_id,
                make_label('OCR Secret Key'),  self._set_ocr_key,
                make_label('企微 Webhook URL'), self._set_webhook,
                make_label('字段映射（JSON）'),  self._set_mapping,
                BoxLayout(size_hint_y=None, height=dp(10)),  # 间距
                btn_row,
            ]
            for w in items:
                inner.add_widget(w)
            inner.bind(minimum_height=inner.setter('height'))

            scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
            scroll.add_widget(inner)

            self.settings_dialog = Popup(
                title='',
                content=scroll,
                size_hint=(0.96, 0.92),
                auto_dismiss=False,
                separator_height=0,
                background='',
                background_color=(1, 1, 1, 1),
            )

            save_btn.bind(on_press=lambda _: self._save_settings_native())
            cancel_btn.bind(on_press=lambda _: self.close_settings_dialog())

            self.settings_dialog.open()
        except Exception as e:
            self.show_dialog(f"打开设置失败: {str(e)}")

    def _save_settings_native(self):
        """保存设置（配合原生 Popup 版本）"""
        global WEWORK_CONFIG
        try:
            new_config = {
                "ocr_secret_id": self._set_ocr_id.text.strip(),
                "ocr_secret_key": self._set_ocr_key.text.strip(),
                "webhook_url": self._set_webhook.text.strip(),
            }
            try:
                mapping_text = self._set_mapping.text.strip()
                new_config["field_mapping"] = json.loads(mapping_text) if mapping_text else WEWORK_CONFIG["field_mapping"]
            except json.JSONDecodeError:
                self.show_dialog("字段映射格式错误，请输入有效的 JSON 格式")
                return

            if not new_config["ocr_secret_id"] or not new_config["ocr_secret_key"] or not new_config["webhook_url"]:
                self.show_dialog("Secret ID、Secret Key、Webhook URL 不能为空")
                return

            if save_config(new_config):
                WEWORK_CONFIG = new_config
                self.ocr_client = None
                self.ocr_credential = None
                self.ocr_credential_create_time = None
                self.close_settings_dialog()
                self.show_dialog("配置保存成功！")
            else:
                self.show_dialog("配置保存失败，请检查存储权限")
        except Exception as e:
            self.show_dialog(f"保存配置失败: {str(e)}")

    def save_settings(self, settings_layout):
        """保存设置（兼容旧调用，转发到 _save_settings_native）"""
        self._save_settings_native()

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