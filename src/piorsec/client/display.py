"""
Video display (Client side).

Renders decoded video frames using PySide6. Designed to support a future
full GUI (connection screen, settings, etc.) built on the same Qt base.
"""

import numpy as np
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QWidget


class VideoWidget(QWidget):
    """Widget that displays raw RGB video frames via QPainter."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image: QImage | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

    def set_frame(self, ndarray: np.ndarray) -> None:
        """Receive a new frame and schedule a repaint.

        Parameters
        ----------
        ndarray:
            H×W×3 uint8 array in RGB format.
        """
        if ndarray is None or ndarray.size == 0:
            return
        h, w, channels = ndarray.shape
        if channels != 3:
            return

        # NumPy array is guaranteed contiguous by to_ndarray(), but enforce just in case
        bytes_per_line = w * 3
        self._image = QImage(ndarray.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ARG002
        with QPainter(self) as painter:
            if self._image is None or self._image.isNull():
                painter.fillRect(self.rect(), Qt.GlobalColor.black)
                return

            # Scale while preserving aspect ratio, centered in widget
            widget_rect = self.rect()
            img_size = self._image.size()
            scaled_size = img_size.scaled(widget_rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
            x = (widget_rect.width() - scaled_size.width()) // 2
            y = (widget_rect.height() - scaled_size.height()) // 2
            target_rect = QRect(x, y, scaled_size.width(), scaled_size.height())
            painter.drawImage(target_rect, self._image)
