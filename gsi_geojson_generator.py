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

from .exlib import tiletanic
from .exlib.shapely import geometry as shapely_geometry
from . import settings


class GsiGeojsonGenerator:
    def __init__(self, leftbottom_lonlat:list, righttop_lonlat:list, layer_key:str, zoomlevel:int):
        self.leftbottom_lonlat = leftbottom_lonlat
        self.righttop_lonlat = righttop_lonlat
        self.layer_key = layer_key
        self.zoomlevel = zoomlevel

        self.run()

    def run(self):
        tileindex = self.make_tileindex()
        indicator = ProgressIndicator(tileindex, self.layer_key)
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
    TMP_GEOJSON_PATH = os.path.join(tempfile.gettempdir(), 'vtdownloader', 'tmp.geojson')
    def __init__(self, tileindex, layer_key):
        super().__init__()
        self.ui = uic.loadUi(os.path.join(os.path.dirname(__file__), 'gsi_geojson_generator_indicator_base.ui'), self)
        self.layer_key = layer_key

        self.dl_progressbar = self.ui.download_progressBar
        self.dcd_progressbar = self.ui.decode_progressBar

        self.tile_downloader = TileDownloader(tileindex)
        self.tile_downloader.progressChanged.connect(self.update_download_progress)
        self.tile_downloader.downloadFinished.connect(self.start_decode)

        self.tile_decoder = TileDecoder(layer_key)
        self.tile_decoder.progressChanged.connect(self.update_decode_progress)
        self.tile_decoder.geojsonCompleted.connect(lambda:self.add_geojson_to_proj())

        self.tile_downloader.start()

    def update_download_progress(self, value):
        self.dl_progressbar.setValue(value)

    def update_decode_progress(self, value):
        self.dcd_progressbar.setValue(value)

    def start_decode(self):
        self.tile_decoder.start()

    def add_geojson_to_proj(self):
        vlayer = QgsVectorLayer(self.tile_decoder.geojson_str, self.layer_key, 'ogr')
        QgsProject.instance().addMapLayer(vlayer)

    def clip_vlayer_by_extent_of(self, leftbottom, righttop, vlayer:QgsVectorLayer):
        pass


class TileDownloader(QThread):
    TMP_PATH = os.path.join(tempfile.gettempdir(), 'vtdownloader')
    TILE_URL = r'https://cyberjapandata.gsi.go.jp/xyz/experimental_bvmap/{z}/{x}/{y}.pbf'
    progressChanged = pyqtSignal(int)
    downloadFinished = pyqtSignal(bool)

    def __init__(self, tileindex):
        super().__init__()
        self.tileindex = tileindex

    def run(self):
        shutil.rmtree(self.TMP_PATH)
        self.make_xyz_dirs()
        for i in range(len(self.tileindex)):
            x = str(self.tileindex[i][0])
            y = str(self.tileindex[i][1])
            z = str(self.tileindex[i][2])
            current_tileurl = self.TILE_URL
            current_tileurl = current_tileurl.replace(r'{z}', z).replace(r'{x}', x).replace(r'{y}', y)
            target_path = os.path.join(self.TMP_PATH, z, x, y + '.pbf')
            urllib.request.urlretrieve(current_tileurl, target_path)
            current_val = int( (i + 1) / len(self.tileindex) * 100 )
            self.progressChanged.emit(current_val)

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

    def __init__(self, layer_key):
        super().__init__()
        self.layer_key = layer_key
        self.geojson_str = ''

    def run(self):
        geojson = self.decode_to_geojson()
        self.geojson_str = json.dumps(geojson, ensure_ascii=False)
        self.geojsonCompleted.emit(True)

    def decode_to_geojson(self):
        z = os.listdir(self.TMP_PATH)[0]
        x_dirs = os.listdir(os.path.join(self.TMP_PATH, z))
        pbf_paths = []
        for x in x_dirs:
            pbf_paths += glob.glob(os.path.join(self.TMP_PATH, z, x, '*'))
        
        #decoding start
        decoded_features = []
        for i in range(len(pbf_paths)):
            pbf = pbf_paths[i]
            z = pbf.split(os.sep)[-3]
            x = pbf.split(os.sep)[-2]
            y = pbf.split(os.sep)[-1].split('.')[0]
        
            tippecanoe_path = '"' + os.path.join(os.path.dirname(os.path.realpath(__file__)), 'exlib', 'tippecanoe-decode') + '"'
            tippicanoe_output = subprocess.getoutput(
                tippecanoe_path + ' '
                + pbf + ' '
                + z + ' '
                + x + ' '
                + y + ' '
                + '--layer=' + self.layer_key)
            output_dict = json.loads(tippicanoe_output)
            
            if output_dict['features']:
                decoded_features += output_dict['features'][0]['features']
            
            current_val = int( (i + 1) / len(pbf_paths) * 100 )
            self.progressChanged.emit(current_val)
        
        geojson = {
            'type':'FeatureCollection',
            'features':decoded_features
        }
        return geojson