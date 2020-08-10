from qgis.PyQt.QtCore import QVariant

SOURCE_LAYERS = {
    'symbol': {
        'category': '記号',
        'datatype': '点',
        'minzoom': 4,
        'maxzoom': 16
    },
    'boundary': {
        'category': '境界',
        'datatype': '線',
        'minzoom': 4,
        'maxzoom': 16
    },
    'road': {
        'category': '道路',
        'datatype': '線',
        'minzoom': 6,
        'maxzoom': 16
    },
    'railway': {
        'category': '鉄道',
        'datatype': '線',
        'minzoom': 6,
        'maxzoom': 16
    },
    'searoute': {
        'category': '航路',
        'datatype': '線',
        'minzoom': 4,
        'maxzoom': 16
    },
    'building': {
        'category': '建物',
        'datatype': '面',
        'minzoom': 13,
        'maxzoom': 16
    },
    'transp': {
        'category': '交通構造物',
        'datatype': '点',
        'minzoom': 11,
        'maxzoom': 16
    },
    'transl': {
        'category': '交通構造物',
        'datatype': '線',
        'minzoom': 14,
        'maxzoom': 16
    },
    'structurel': {
        'category': '構造物',
        'datatype': '線',
        'minzoom': 14,
        'maxzoom': 16
    },
    'structurea': {
        'category': '構造物',
        'datatype': '面',
        'minzoom': 11,
        'maxzoom': 16
    },
    'coastline': {
        'category': '海岸線',
        'datatype': '線',
        'minzoom': 4,
        'maxzoom': 16
    },
    'river': {
        'category': '河川',
        'datatype': '線',
        'minzoom': 6,
        'maxzoom': 16
    },
    'lake': {
        'category': '湖池',
        'datatype': '線',
        'minzoom': 4,
        'maxzoom': 16
    },
    'waterarea': {
        'category': '水域',
        'datatype': '面',
        'minzoom': 4,
        'maxzoom': 16
    },
    'elevation': {
        'category': '標高点',
        'datatype': '点',
        'minzoom': 6,
        'maxzoom': 16
    },
    'contour': {
        'category': '等高線等深線',
        'datatype': '線',
        'minzoom': 11,
        'maxzoom': 16
    },
    'landformp': {
        'category': '地形',
        'datatype': '点',
        'minzoom': 14,
        'maxzoom': 16
    },
    'landforml': {
        'category': '地形',
        'datatype': '線',
        'minzoom': 14,
        'maxzoom': 16
    },
    'landforma': {
        'category': '地形',
        'datatype': '面',
        'minzoom': 11,
        'maxzoom': 16
    },
    'label': {
        'category': '注記',
        'datatype': '点',
        'minzoom': 4,
        'maxzoom': 16
    }
}

#データ型をDoubleにすべきフィールド名
DOUBLE_FIELDS = [
    "arrngAgl",
    "alti",
    "depth"
]
