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


class LSarea(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMapLayer('filleddem', 'Filled DEM no nulls or sinks', defaultValue=None, types=[QgsProcessing.TypeRaster]))
        self.addParameter(QgsProcessingParameterNumber('lssheeterosionfactor', 'LS sheet erosion factor', optional=True, type=QgsProcessingParameterNumber.Double, minValue=0.4, maxValue=0.6, defaultValue=0.5))
        self.addParameter(QgsProcessingParameterNumber('lsrillerosionfactor', 'LS rill erosion factor', optional=True, type=QgsProcessingParameterNumber.Double, minValue=1, maxValue=1.3, defaultValue=1.1))
        self.addParameter(QgsProcessingParameterRasterDestination('Ls', 'LS', createByDefault=True, defaultValue=None))
        self.addParameter(QgsProcessingParameterRasterDestination('Slope', 'Slope', createByDefault=True, defaultValue=None))
        self.addParameter(QgsProcessingParameterRasterDestination('FlowAccumulation', 'Flow Accumulation', createByDefault=True, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(2, model_feedback)
        results = {}
        outputs = {}

        # Slope
        alg_params = {
            'INPUT': parameters['filleddem'],
            'Z_FACTOR': 1,
            'OUTPUT': parameters['Slope']
        }
        outputs['Slope'] = processing.run('native:slope', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Slope'] = outputs['Slope']['OUTPUT']

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # Flow Accumulation (Top-Down)
        alg_params = {
            'ACCU_MATERIAL': None,
            'ACCU_TARGET': parameters['filleddem'],
            'CONVERGENCE': 1.1,
            'ELEVATION': parameters['filleddem'],
            'FLOW_UNIT': 1,  # [1] cell area
            'LINEAR_DIR': None,
            'LINEAR_DO': False,
            'LINEAR_MIN': 500,
            'LINEAR_VAL': None,
            'METHOD': 4,  # [4] Multiple Flow Direction
            'NO_NEGATIVES': True,
            'SINKROUTE': None,
            'STEP': 1,
            'VAL_INPUT': None,
            'WEIGHTS': None,
            'ACCU_LEFT': QgsProcessing.TEMPORARY_OUTPUT,
            'ACCU_RIGHT': QgsProcessing.TEMPORARY_OUTPUT,
            'ACCU_TOTAL': QgsProcessing.TEMPORARY_OUTPUT,
            'FLOW': parameters['FlowAccumulation'],
            'FLOW_LENGTH': QgsProcessing.TEMPORARY_OUTPUT,
            'VAL_MEAN': QgsProcessing.TEMPORARY_OUTPUT,
            'WEIGHT_LOSS': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['FlowAccumulationTopdown'] = processing.run('saga:flowaccumulationtopdown', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['FlowAccumulation'] = outputs['FlowAccumulationTopdown']['FLOW']

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        m = str(parameters['lssheeterosionfactor'])
        n = str(parameters['lsrillerosionfactor'])

        # Raster calculator
        alg_params = {
            'BAND_A': 1,
            'BAND_B': 1,
            'BAND_C': None,
            'BAND_D': None,
            'BAND_E': None,
            'BAND_F': None,
            'EXTRA': '',
            'FORMULA': '(' + m + '1) * power((A/22.1), ' + m + ') * power((sin(B* 3.14159 / 180)/0.09), ' + n + ')',
            'INPUT_A': outputs['FlowAccumulationTopdown']['FLOW'],
            'INPUT_B': outputs['Slope']['OUTPUT'],
            'INPUT_C': None,
            'INPUT_D': None,
            'INPUT_E': None,
            'INPUT_F': None,
            'NO_DATA': None,
            'OPTIONS': '',
            'RTYPE': 5,  # Float32
            'OUTPUT': parameters['Ls']
        }
        outputs['RasterCalculator'] = processing.run('gdal:rastercalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Ls'] = outputs['RasterCalculator']['OUTPUT']

        global outputRenamer
        outputRenamer = OutputRenamer('LSarea')
        context.layerToLoadOnCompletionDetails(results['Ls']).setPostProcessor(outputRenamer)

        return results

    def name(self):
        return 'LSArea'

    def displayName(self):
        return 'LS Area'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return LSarea()

class OutputRenamer (QgsProcessingLayerPostProcessorInterface):
    def __init__(self, layer_name):
        self.name = layer_name
        super().__init__()
        
    def postProcessLayer(self, layer, context, feedback):
        layer.setName(self.name)
