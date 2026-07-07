from __future__ import annotations

import base64
import uuid
from pathlib import Path

from astrbot.api import logger

try:
    from ..constants import IMAGE_KINDS
except ImportError:
    from constants import IMAGE_KINDS


class PageApiMixin:
    async def page_layout(self):
        try:
            from quart import request

            if request.method == "POST":
                if not self._is_same_origin_request(request):
                    return self._json_response({"status": "error", "message": "请求来源无效"})
                payload = await request.get_json(silent=True)
                if not isinstance(payload, dict):
                    payload = {}
                layout = payload.get("layout") if isinstance(payload.get("layout"), dict) else payload
                self.page_settings.update(self._sanitize_layout_settings(layout))
                self._save_page_settings()
                return self._json_response({"status": "ok", "message": "布局已保存", "data": self._page_data()})

            return self._json_response({"status": "ok", "data": self._page_data()})
        except Exception as exc:
            logger.error(f"[谁艾特我] Page布局接口失败: {exc}", exc_info=True)
            return self._json_response({"status": "error", "message": "布局接口失败"})

    async def page_fonts(self):
        try:
            return self._json_response({"status": "ok", "data": self._font_data()})
        except Exception as exc:
            logger.error(f"[谁艾特我] Page字体列表失败: {exc}", exc_info=True)
            return self._json_response({"status": "error", "message": "获取字体列表失败"})

    async def page_font_upload(self):
        try:
            from quart import request

            if not self._is_same_origin_request(request):
                return self._json_response({"status": "error", "message": "请求来源无效"})

            filename = ""
            data = None
            files = await request.files
            file = files.get("font") if files else None
            if file and getattr(file, "filename", ""):
                filename = str(file.filename)
                data = file.read()
                if hasattr(data, "__await__"):
                    data = await data
            else:
                payload = await request.get_json(silent=True)
                if isinstance(payload, dict):
                    filename = str(payload.get("filename") or "")
                    content = str(payload.get("content") or "")
                    if "," in content:
                        content = content.split(",", 1)[1]
                    try:
                        data = base64.b64decode(content, validate=True)
                    except Exception:
                        return self._json_response({"status": "error", "message": "字体文件内容无效"})

            if not filename:
                return self._json_response({"status": "error", "message": "请选择字体文件"})
            if not self._is_allowed_font_file(filename):
                return self._json_response({"status": "error", "message": "仅支持 .ttf/.otf/.woff/.woff2/.ttc 字体文件"})
            if not data:
                return self._json_response({"status": "error", "message": "字体文件为空"})
            if len(data) > 50 * 1024 * 1024:
                return self._json_response({"status": "error", "message": "字体文件不能超过50MB"})

            fonts_dir = self._fonts_dir()
            fonts_dir.mkdir(parents=True, exist_ok=True)
            safe_name = self._sanitize_font_filename(filename)
            target = fonts_dir / safe_name
            if target.exists():
                target = fonts_dir / f"{target.stem}_{uuid.uuid4().hex[:8]}{target.suffix}"
            target.write_bytes(data)

            self._save_font_path(self._font_config_path(target.name))
            logger.info(f"[谁艾特我] Page上传并启用自定义字体: {target.name}")
            return self._json_response({"status": "ok", "message": "字体已上传并启用", "data": self._font_data()})
        except Exception as exc:
            logger.error(f"[谁艾特我] Page上传字体失败: {exc}", exc_info=True)
            return self._json_response({"status": "error", "message": "上传字体失败"})

    async def page_font_select(self):
        try:
            from quart import request

            if not self._is_same_origin_request(request):
                return self._json_response({"status": "error", "message": "请求来源无效"})

            payload = await request.get_json(silent=True)
            font_path = str((payload.get("font_path") or "") if isinstance(payload, dict) else "").strip()
            if font_path:
                font_name = self._sanitize_font_filename(self._selected_font_name(font_path))
                if not font_name or not self._is_allowed_font_file(font_name):
                    return self._json_response({"status": "error", "message": "字体文件类型不支持"})
                target = self._fonts_dir() / font_name
                if not target.exists() or not target.is_file():
                    return self._json_response({"status": "error", "message": "字体文件不存在"})
                font_path = self._font_config_path(font_name)

            self._save_font_path(font_path)
            logger.info(f"[谁艾特我] Page切换自定义字体: {font_path or '默认字体'}")
            return self._json_response({"status": "ok", "message": "字体设置已保存", "data": self._font_data()})
        except Exception as exc:
            logger.error(f"[谁艾特我] Page选择字体失败: {exc}", exc_info=True)
            return self._json_response({"status": "error", "message": "保存字体设置失败"})

    async def page_font_delete(self):
        try:
            from quart import request

            if not self._is_same_origin_request(request):
                return self._json_response({"status": "error", "message": "请求来源无效"})

            payload = await request.get_json(silent=True)
            font_path = str((payload.get("font_path") or "") if isinstance(payload, dict) else "").strip()
            font_name = self._sanitize_font_filename(self._selected_font_name(font_path))
            if not font_name or not self._is_allowed_font_file(font_name):
                return self._json_response({"status": "error", "message": "字体文件参数无效"})
            target = self._fonts_dir() / font_name
            if not target.exists() or not target.is_file():
                return self._json_response({"status": "error", "message": "字体文件不存在"})

            target.unlink()
            if self._selected_font_name(self.page_settings.get("font_path", "")) == font_name:
                self._save_font_path("")
            logger.info(f"[谁艾特我] Page删除自定义字体: {font_name}")
            return self._json_response({"status": "ok", "message": "字体已删除", "data": self._font_data()})
        except Exception as exc:
            logger.error(f"[谁艾特我] Page删除字体失败: {exc}", exc_info=True)
            return self._json_response({"status": "error", "message": "删除字体失败"})

    async def page_image_upload(self):
        try:
            from quart import request

            if not self._is_same_origin_request(request):
                return self._json_response({"status": "error", "message": "请求来源无效"})

            kind = ""
            filename = ""
            data = None
            files = await request.files
            file = files.get("image") if files else None
            if file and getattr(file, "filename", ""):
                filename = str(file.filename)
                form = await request.form
                kind = str(form.get("kind") or "")
                data = file.read()
                if hasattr(data, "__await__"):
                    data = await data
            else:
                payload = await request.get_json(silent=True)
                if isinstance(payload, dict):
                    kind = str(payload.get("kind") or "")
                    filename = str(payload.get("filename") or "")
                    content = str(payload.get("content") or "")
                    if "," in content:
                        content = content.split(",", 1)[1]
                    try:
                        data = base64.b64decode(content, validate=True)
                    except Exception:
                        return self._json_response({"status": "error", "message": "图片文件内容无效"})

            kind = kind.strip().lower()
            if kind not in IMAGE_KINDS:
                return self._json_response({"status": "error", "message": "图片类型无效"})
            if not filename:
                return self._json_response({"status": "error", "message": "请选择图片文件"})
            if not self._is_allowed_image_file(filename):
                return self._json_response({"status": "error", "message": "仅支持 .png/.jpg/.jpeg/.webp/.gif 图片"})
            if not data:
                return self._json_response({"status": "error", "message": "图片文件为空"})
            if len(data) > 15 * 1024 * 1024:
                return self._json_response({"status": "error", "message": "图片文件不能超过15MB"})

            images_dir = self._images_dir()
            images_dir.mkdir(parents=True, exist_ok=True)
            suffix = Path(filename).suffix.lower()
            target = images_dir / f"{kind}{suffix}"
            for old in images_dir.glob(f"{kind}.*"):
                try:
                    if old.is_file():
                        old.unlink()
                except OSError:
                    pass
            target.write_bytes(data)

            self._save_image_path(kind, self._image_config_path(target.name))
            logger.info(f"[谁艾特我] Page上传并启用自定义{IMAGE_KINDS[kind]}: {target.name}")
            return self._json_response({"status": "ok", "message": "图片已上传并启用", "data": self._page_data()})
        except Exception as exc:
            logger.error(f"[谁艾特我] Page上传图片失败: {exc}", exc_info=True)
            return self._json_response({"status": "error", "message": "上传图片失败"})

    async def page_image_reset(self):
        try:
            from quart import request

            if not self._is_same_origin_request(request):
                return self._json_response({"status": "error", "message": "请求来源无效"})

            payload = await request.get_json(silent=True)
            kind = str((payload.get("kind") or "") if isinstance(payload, dict) else "").strip().lower()
            kinds = [kind] if kind in IMAGE_KINDS else list(IMAGE_KINDS)
            for item in kinds:
                self._save_image_path(item, "", save=False)
            self._save_page_settings()
            return self._json_response({"status": "ok", "message": "图片已恢复默认", "data": self._page_data()})
        except Exception as exc:
            logger.error(f"[谁艾特我] Page恢复默认图片失败: {exc}", exc_info=True)
            return self._json_response({"status": "error", "message": "恢复默认图片失败"})
