"""
/***************************************************************************
ErosionFlow
 A QGIS plugin with QGIS : 32214
 Provides Basic erosion processing algorithms, such as RUSLE AND USPED
                              -------------------
        begin                : 2023-03-28
        copyright            : (C) 2023 by Michael Tuck
        email                : contact@michaeltuck.com
        MIT LICENCE                                                         
 ***************************************************************************/
"""

from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterMapLayer
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingParameterRasterDestination
from qgis.core import QgsProcessingLayerPostProcessorInterface
import processing


class RUSLE(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMapLayer('filledsinksdem', 'Filled sinks DEM', defaultValue=None, types=[QgsProcessing.TypeRaster]))
        self.addParameter(QgsProcessingParameterMapLayer('kfactor', 'K factor raster', optional=True, defaultValue=None, types=[QgsProcessing.TypeRaster]))
        self.addParameter(QgsProcessingParameterMapLayer('cfactor', 'C factor raster', optional=True, defaultValue=None, types=[QgsProcessing.TypeRaster]))
        self.addParameter(QgsProcessingParameterMapLayer('rfactor', 'R factor raster', optional=True, defaultValue=None, types=[QgsProcessing.TypeRaster]))
        self.addParameter(QgsProcessingParameterNumber('kfactorsinglevalue', 'K factor single value', optional=True, type=QgsProcessingParameterNumber.Double, defaultValue=0.05))
        self.addParameter(QgsProcessingParameterNumber('cfactorsinglevalue', 'C factor single value', optional=True, type=QgsProcessingParameterNumber.Double, defaultValue=0.5))
        self.addParameter(QgsProcessingParameterNumber('rfactorsinglevalue', 'R factor single value', optional=True, type=QgsProcessingParameterNumber.Double, defaultValue=750))
        self.addParameter(QgsProcessingParameterNumber('lssheetfactor', 'LS sheet factor', optional=True, type=QgsProcessingParameterNumber.Double, minValue=0.4, maxValue=0.6, defaultValue=0.5))
        self.addParameter(QgsProcessingParameterNumber('lsrillfactor', 'LS rill factor', optional=True, type=QgsProcessingParameterNumber.Double, minValue=1, maxValue=1.3, defaultValue=1.1))
        self.addParameter(QgsProcessingParameterRasterDestination('LSArea', 'LS Area'))
        self.addParameter(QgsProcessingParameterRasterDestination('Rusle', 'RUSLE'))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(2, model_feedback)
        results = {}
        outputs = {}

        # LS Mitasova
        alg_params = {
            'filleddem': parameters['filledsinksdem'],
            'lsrillerosionfactor': parameters['lsrillfactor'],
            'lssheeterosionfactor': parameters['lssheetfactor'],
            'FlowAccumulation': QgsProcessing.TEMPORARY_OUTPUT,
            'Ls': QgsProcessing.TEMPORARY_OUTPUT,
            'Slope': parameters['LSArea']
        }
        outputs['LsMitasova'] = processing.run('script:LS Mitasova', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['LSArea'] = outputs['LsMitasova']['Ls']

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        feedback.pushConsoleInfo('\n~~~~~~~~~~~~~~~~ RUSLE FORMULA ~~~~~~~~~~~~~~~~\n')

        # build raster calculation using single factors or rasters
        RUSLEformula = 'A*'
        if parameters['kfactor'] is not None: 
            RUSLEformula += 'B*'
        else: 
            RUSLEformula += str(parameters['kfactorsinglevalue'])+'*'
        if parameters['cfactor'] is not None: 
            RUSLEformula += 'C*'
        else: 
            RUSLEformula += str(parameters['cfactorsinglevalue'])+'*'
        if parameters['rfactor'] is not None: 
            RUSLEformula += 'D'
        else: 
            RUSLEformula += str(parameters['rfactorsinglevalue'])

        feedback.pushConsoleInfo(RUSLEformula+'\n')

        # Raster calculator
        alg_params = {
            'BAND_A': 1,
            'BAND_B': 1,
            'BAND_C': 1,
            'BAND_D': 1,
            'BAND_E': None,
            'BAND_F': None,
            'EXTRA': '',
            'FORMULA': RUSLEformula,
            'INPUT_A': outputs['LsMitasova']['Ls'],
            'INPUT_B': parameters['kfactor'],
            'INPUT_C': parameters['cfactor'],
            'INPUT_D': parameters['rfactor'],
            'INPUT_E': None,
            'INPUT_F': None,
            'NO_DATA': None,
            'OPTIONS': '',
            'RTYPE': 6,  # Float64
            'OUTPUT': parameters['Rusle']
        }
        outputs['RasterCalculator'] = processing.run('gdal:rastercalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Rusle'] = outputs['RasterCalculator']['OUTPUT']

        global renamer
        renamer = Renamer('RUSLE')
        context.layerToLoadOnCompletionDetails(results['Rusle']).setPostProcessor(renamer)

        return results

    def name(self):
        return 'RUSLE'

    def displayName(self):
        return 'RUSLE'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return RUSLE()

class Renamer (QgsProcessingLayerPostProcessorInterface):
    def __init__(self, layer_name):
        self.name = layer_name
        super().__init__()
        
    def postProcessLayer(self, layer, context, feedback):
        layer.setName(self.name)
