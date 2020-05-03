import os
import math
import time
import tempfile
import shutil
import urllib
import glob
import subprocess
import json

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import QThread, pyqtSignal
from qgis.core import QgsProject, QgsVectorLayer
import processing

from .exlib import tiletanic
from .exlib.shapely import geometry as shapely_geometry
from . import settings


class GsiGeojsonGenerator:
    def __init__(self, leftbottom_lonlat:list, righttop_lonlat:list, layer_key:str, zoomlevel:int, clipmode=False):
        self.leftbottom_lonlat = leftbottom_lonlat
        self.righttop_lonlat = righttop_lonlat
        self.layer_key = layer_key
        self.zoomlevel = zoomlevel
        self.clipmode = clipmode

        self.run()

    def run(self):
        tileindex = self.make_tileindex()

        bbox_xyMinMax = None
        if self.clipmode:
            xMin = self.leftbottom_lonlat[0]
            xMax = self.righttop_lonlat[0]
            yMin = self.leftbottom_lonlat[1]
            yMax = self.righttop_lonlat[1]
            bbox_xyMinMax = [xMin, xMax, yMin, yMax]

        indicator = ProgressIndicator(tileindex, self.layer_key, bbox_xyMinMax)
        indicator.show()

    def make_tileindex(self):
        leftbottom_as_3857 = self.lonlat_to_webmercator(self.leftbottom_lonlat)
        righttop_as_3857 = self.lonlat_to_webmercator(self.righttop_lonlat)
        bbox_geometry = self.make_rectangle_of(leftbottom_as_3857, righttop_as_3857)

        tiler = tiletanic.tileschemes.WebMercator()
        feature_shape = shapely_geometry.shape(bbox_geometry)

        covering_tiles_itr = tiletanic.tilecover.cover_geometry(tiler, feature_shape, self.zoomlevel)
        covering_tiles = []
        for tile in covering_tiles_itr:
            tile_xyz = [tile[0], tile[1], tile[2]]
            covering_tiles.append(tile_xyz)

        return covering_tiles

    def lonlat_to_webmercator(self, lonlat):
        return [lonlat[0] * 20037508.34 / 180,
                math.log(math.tan( (90 + lonlat[1]) * math.pi / 360) ) / (math.pi / 180) * 20037508.34 / 180]

    def make_rectangle_of(self, leftbottom, righttop):
        x1 = leftbottom[0]
        y1 = leftbottom[1]
        x2 = righttop[0]
        y2 = righttop[1]
        rectangle = {
            'type':'Polygon',
            'coordinates':[
                [
                    [x1, y1], [x2, y1],
                    [x2, y2], [x1, y2], [x1, y1]
                ]
            ]
        }
        return rectangle


class ProgressIndicator(QtWidgets.QDialog):
    def __init__(self, tileindex, layer_key, bbox_xyMinMax=None):
        super().__init__()
        self.ui = uic.loadUi(os.path.join(os.path.dirname(__file__), 'gsi_geojson_generator_indicator_base.ui'), self)
        self.layer_key = layer_key
        self.tileindex = tileindex
        self.bbox_xyMinMax = bbox_xyMinMax

        self.ui.abortPushButton.clicked.connect(self.on_abort_pushbutton_clicked)

        self.dl_progressbar = self.ui.download_progressBar
        self.dl_progressbar.setRange(0, len(self.tileindex))
        self.dl_progressbar.setFormat('%v/%m(%p%)')
        self.dcd_progressbar = self.ui.decode_progressBar
        self.dcd_progressbar.setRange(0, len(self.tileindex))
        self.dcd_progressbar.setFormat('%v/%m(%p%)')

        self.tile_downloader = TileDownloader(tileindex)
        self.tile_downloader.progressChanged.connect(self.update_download_progress)
        self.tile_downloader.downloadFinished.connect(self.start_decode)

        self.tile_decoder = TileDecoder(tileindex, layer_key)
        self.tile_decoder.progressChanged.connect(self.update_decode_progress)
        self.tile_decoder.geojsonCompleted.connect(lambda:self.add_geojson_to_proj())
        
        self.tile_downloader.start()

    def update_download_progress(self, value:int):
        self.dl_progressbar.setValue(value)

    def update_decode_progress(self, value:int):
        self.dcd_progressbar.setValue(value)

    def start_decode(self):
        self.tile_decoder.start()

    def add_geojson_to_proj(self):
        vlayer = QgsVectorLayer(self.tile_decoder.geojson_str, self.layer_key, 'ogr')

        if self.bbox_xyMinMax:
            vlayer = self.clip_vlayer(vlayer)
        
        QgsProject.instance().addMapLayer(vlayer)
        QtWidgets.QMessageBox.information(None, 'GSI-VTDownloader', 'Completed')
        self.close()

    def clip_vlayer(self, vlayer:QgsVectorLayer)->QgsVectorLayer:
        cliped = processing.run('qgis:extractbyextent', {
            'INPUT':vlayer,
            'CLIP':False,
            'EXTENT':'%s,%s,%s,%s'%(self.bbox_xyMinMax[0],
                                    self.bbox_xyMinMax[1], 
                                    self.bbox_xyMinMax[2], 
                                    self.bbox_xyMinMax[3]),
            'OUTPUT':'memory:'
        })['OUTPUT']
        return cliped

    def on_abort_pushbutton_clicked(self):
        self.tile_downloader.quit()
        self.tile_decoder.quit()
        QtWidgets.QMessageBox.information(None, 'GSI-VTDownloader', '処理を中止しました')
        self.close()


class TileDownloader(QThread):
    TMP_PATH = os.path.join(tempfile.gettempdir(), 'vtdownloader')
    TILE_URL = r'https://cyberjapandata.gsi.go.jp/xyz/experimental_bvmap/{z}/{x}/{y}.pbf'
    progressChanged = pyqtSignal(int)
    downloadFinished = pyqtSignal(bool)

    def __init__(self, tileindex):
        super().__init__()
        self.tileindex = tileindex
        os.makedirs(os.path.join(self.TMP_PATH), exist_ok=True)

    def run(self):
        self.make_xyz_dirs()
        for i in range(len(self.tileindex)):
            xyz = self.tileindex[i]
            x = str(xyz[0])
            y = str(xyz[1])
            z = str(xyz[2])
            current_tileurl = self.TILE_URL
            current_tileurl = current_tileurl.replace(r'{z}', z).replace(r'{x}', x).replace(r'{y}', y)
            target_path = os.path.join(self.TMP_PATH, z, x, y + '.pbf')
            
            #download New file only
            if not os.path.exists(target_path):
                urllib.request.urlretrieve(current_tileurl, target_path)

            self.progressChanged.emit(i + 1)

        self.downloadFinished.emit(True)

    def make_xyz_dirs(self):
        for xyz in self.tileindex:
            x = str(xyz[0])
            z = str(xyz[2])
            os.makedirs(os.path.join(self.TMP_PATH, z, x), exist_ok=True)


class TileDecoder(QThread):
    TMP_PATH = os.path.join(tempfile.gettempdir(), 'vtdownloader')
    progressChanged = pyqtSignal(int)
    geojsonCompleted = pyqtSignal(bool)

    def __init__(self, tileindex, layer_key):
        super().__init__()
        self.tileindex = tileindex
        self.layer_key = layer_key
        self.geojson_str = ''

    def run(self):
        geojson = self.decode_to_geojson()
        self.geojson_str = json.dumps(geojson, ensure_ascii=False)
        self.geojsonCompleted.emit(True)

    def decode_to_geojson(self):
        #decoding start
        decoded_features = []
        for i in range(len(self.tileindex)):
            xyz = self.tileindex[i]
            x = str(xyz[0])
            y = str(xyz[1])
            z = str(xyz[2])

            pbffile = os.path.join(self.TMP_PATH, z, x, y + '.pbf')
        
            tippecanoe_path = '"' + os.path.join(os.path.dirname(os.path.realpath(__file__)), 'exlib', 'tippecanoe-decode') + '"'
            tippicanoe_output = subprocess.getoutput(
                tippecanoe_path + ' '
                + pbffile + ' '
                + z + ' '
                + x + ' '
                + y + ' '
                + '--layer=' + self.layer_key)
            output_dict = json.loads(tippicanoe_output)
            
            if output_dict['features']:
                decoded_features += output_dict['features'][0]['features']
            
            self.progressChanged.emit(i + 1)
        
        geojson = {
            'type':'FeatureCollection',
            'features':decoded_features
        }
        return geojson
