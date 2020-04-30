from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from qgis.core import *
from qgis.gui import *

class RubberbandMapTool(QgsMapTool):
    def __init__(self, iface, callback):
        QgsMapTool.__init__(self, iface.mapCanvas())
        self.iface      = iface
        self.callback   = callback
        self.canvas     = iface.mapCanvas()
        self.startpoint = None
        self.rubberband = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        return None

    def canvasPressEvent(self,e):
        self.startpoint = QPoint(e.pos().x(),e.pos().y())
        return None

    def canvasMoveEvent(self,e):
        self.rubberband.reset(QgsWkbTypes.PolygonGeometry)

        currentpoint = QPoint(e.pos().x(),e.pos().y())
        vertexes = self.get_current_vertexes(currentpoint)
        for v in vertexes:
            self.rubberband.addPoint(v, True)
        
        self.rubberband.show()
        return None

    def canvasReleaseEvent(self,e):
        endpoint = QPoint(e.pos().x(),e.pos().y())

        start_pointxy = self.canvas.getCoordinateTransform().toMapPoint(self.startpoint.x(), self.startpoint.y())
        end_pointxy = self.canvas.getCoordinateTransform().toMapPoint(endpoint.x(), endpoint.y())

        start_qgspoint = QgsPoint(start_pointxy.x(), start_pointxy.y())
        end_qgspoint = QgsPoint(end_pointxy.x(), end_pointxy.y())

        self.callback(start_qgspoint, end_qgspoint)

        self.startpoint = None
        self.rubberband.reset(QgsWkbTypes.PolygonGeometry)
        return None

    def get_current_vertexes(self, currentpoints):
        if self.startpoint and currentpoints:
            p1 = self.canvas.getCoordinateTransform().toMapPoint(self.startpoint.x(), self.startpoint.y())
            p2 = self.canvas.getCoordinateTransform().toMapPoint(currentpoints.x(), self.startpoint.y())
            p3 = self.canvas.getCoordinateTransform().toMapPoint(currentpoints.x(), currentpoints.y())
            p4 = self.canvas.getCoordinateTransform().toMapPoint(self.startpoint.x(), currentpoints.y())
            return [p1, p2, p3, p4]
        return []