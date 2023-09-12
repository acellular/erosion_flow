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
from qgis.core import QgsProcessingParameterBoolean
import processing


class USPED(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMapLayer('filleddem', 'Filled sinks DEM', defaultValue=None, types=[QgsProcessing.TypeRaster]))
        self.addParameter(QgsProcessingParameterMapLayer('kfactor', 'K factor raster', optional=True, defaultValue=None, types=[QgsProcessing.TypeRaster]))
        self.addParameter(QgsProcessingParameterMapLayer('cfactor', 'C factor raster', optional=True, defaultValue=None, types=[QgsProcessing.TypeRaster]))
        self.addParameter(QgsProcessingParameterMapLayer('rfactor', 'R factor raster', optional=True, defaultValue=None, types=[QgsProcessing.TypeRaster]))
        self.addParameter(QgsProcessingParameterNumber('kfactorsinglevalue', 'K factor single value', optional=True, type=QgsProcessingParameterNumber.Double, defaultValue=0.05))
        self.addParameter(QgsProcessingParameterNumber('cfactorsinglevalue', 'C factor single value', optional=True, type=QgsProcessingParameterNumber.Double, defaultValue=0.5))
        self.addParameter(QgsProcessingParameterNumber('rfactorsinglevalue', 'R factor single value', optional=True, type=QgsProcessingParameterNumber.Double, defaultValue=750))
        self.addParameter(QgsProcessingParameterNumber('lssheetfactor', 'LS sheet factor', optional=True, type=QgsProcessingParameterNumber.Double, minValue=0.4, maxValue=0.6, defaultValue=0.5))
        self.addParameter(QgsProcessingParameterNumber('lsrillfactor', 'LS rill factor', optional=True, type=QgsProcessingParameterNumber.Double, minValue=1, maxValue=1.3, defaultValue=1.1))
        self.addParameter(QgsProcessingParameterBoolean('prevailingrill', 'Prevailing rill erosion (unchecked for sheet)', defaultValue=True))
        self.addParameter(QgsProcessingParameterRasterDestination('FlowAccumulation', 'Flow Accumulation', createByDefault=True, defaultValue=None))
        self.addParameter(QgsProcessingParameterRasterDestination('Usped', 'USPED'))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(6, model_feedback)
        results = {}
        outputs = {}

        # convert to bool
        prevailingRill = self.parameterAsBool(parameters, 'prevailingrill', context)
        feedback.pushConsoleInfo('Prevailing rill? ' + str(prevailingRill))

        # STEP 1: following from http://fatra.cnr.ncsu.edu/~hmitaso/gmslab/denix/usped.html
        # Slope
        alg_params = {
            'INPUT': parameters['filleddem'],
            'Z_FACTOR': 1,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Slope'] = processing.run('native:slope', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        # Aspect
        alg_params = {
            'INPUT': parameters['filleddem'],
            'Z_FACTOR': 1,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Aspect'] = processing.run('native:aspect', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}
        feedback.pushConsoleInfo('\n~~~ Step 1: Flow accumulation (area) ~~~\n')

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


        feedback.pushConsoleInfo('\n~~~~~~~~~~~~~~~~ USPED START ~~~~~~~~~~~~~~~~\n')

        # STEP 2: following from http://fatra.cnr.ncsu.edu/~hmitaso/gmslab/denix/usped.html
        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}
        feedback.pushConsoleInfo('\n~~~ Step 2: sflowtopo ~~~\n')
        # sflowtopo = Pow([flowacc] * resolution , 0.6) * Pow(Sin([slope] * 0.01745) , 1.3))
        # Note: flow accumulation already calculates area so no need for resolution
        if prevailingRill: formula = 'pow(A, 0.6) * pow(sin(B * 0.01745), 1.3)'
        else: formula = 'A * sin(B * 0.01745)'
        alg_params = {
            'BAND_A': 1,
            'BAND_B': 1,
            'BAND_C': 1,
            'BAND_D': 1,
            'BAND_E': None,
            'BAND_F': None,
            'EXTRA': '',
            'FORMULA': formula,
            'INPUT_A': outputs['FlowAccumulationTopdown']['FLOW'],
            'INPUT_B': outputs['Slope']['OUTPUT'],
            'INPUT_C': None,
            'INPUT_D': None,
            'INPUT_E': None,
            'INPUT_F': None,
            'NO_DATA': None,
            'OPTIONS': '',
            'RTYPE': 6,  # Float64
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['sflowtopo'] = processing.run('gdal:rastercalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        # STEP 3: following from http://fatra.cnr.ncsu.edu/~hmitaso/gmslab/denix/usped.html
        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}
          
        # using consts or parameters?
        if parameters['kfactor'] is not None: Kfactor = 'B*'
        else: Kfactor = str(parameters['kfactorsinglevalue'])+'*'
        if parameters['cfactor'] is not None: Cfactor = 'C*'
        else: Cfactor = str(parameters['cfactorsinglevalue'])+'*'
        if parameters['rfactor'] is not None: Rfactor = 'D'
        else: Rfactor = str(parameters['rfactorsinglevalue'])
        factorsFormula = Kfactor + Cfactor + Rfactor
        
        # qsx = [sflowtopo] * [kfac] * [cfac] * R * Cos((([aspect] *  (-1)) + 450) * .01745)
        formula = 'E *' + factorsFormula + ' * cos(((F * -1) + 450) * 0.01745)'
        feedback.pushConsoleInfo('\nqsx formula: ' + formula + '\n')
        alg_params = {
            'BAND_A': 1,
            'BAND_B': 1,
            'BAND_C': 1,
            'BAND_D': 1,
            'BAND_E': None,
            'BAND_F': None,
            'EXTRA': '',
            'FORMULA': formula,
            'INPUT_A': parameters['filleddem'],
            'INPUT_B': parameters['kfactor'],
            'INPUT_C': parameters['cfactor'],
            'INPUT_D': parameters['rfactor'],
            'INPUT_E': outputs['sflowtopo']['OUTPUT'],
            'INPUT_F': outputs['Aspect']['OUTPUT'],
            'NO_DATA': None,
            'OPTIONS': '',
            'RTYPE': 6,  # Float64
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['qsx'] = processing.run('gdal:rastercalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)


        # qsy = [sflowtopo] * [kfac] * [cfac] * 280 * Sin((([aspect] *  (-1)) + 450) * .01745)
        formula = 'E *' + factorsFormula + ' * sin(((F * -1) + 450) * 0.01745)'
        feedback.pushConsoleInfo('\nqsy formula: ' + formula + '\n')
        alg_params = {
            'BAND_A': 1,
            'BAND_B': 1,
            'BAND_C': 1,
            'BAND_D': 1,
            'BAND_E': None,
            'BAND_F': None,
            'EXTRA': '',
            'FORMULA': formula,
            'INPUT_A': parameters['filleddem'],
            'INPUT_B': parameters['kfactor'],
            'INPUT_C': parameters['cfactor'],
            'INPUT_D': parameters['rfactor'],
            'INPUT_E': outputs['sflowtopo']['OUTPUT'],
            'INPUT_F': outputs['Aspect']['OUTPUT'],
            'NO_DATA': None,
            'OPTIONS': '',
            'RTYPE': 6,  # Float64
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['qsy'] = processing.run('gdal:rastercalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Usped'] = outputs['qsy']['OUTPUT']
        

        # STEP 4: following from http://fatra.cnr.ncsu.edu/~hmitaso/gmslab/denix/usped.html
        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}
        feedback.pushConsoleInfo('\n~~~ Step 4: Slope and aspect of qsx and qy ~~~\n')
        # Slope qsx
        alg_params = {
            'INPUT': outputs['qsx']['OUTPUT'],
            'Z_FACTOR': 1,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['qsxSlope'] = processing.run('native:slope', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        # Aspect qsx
        alg_params = {
            'INPUT': outputs['qsx']['OUTPUT'],
            'Z_FACTOR': 1,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['qsxAspect'] = processing.run('native:aspect', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        # STEP 5: following from http://fatra.cnr.ncsu.edu/~hmitaso/gmslab/denix/usped.html
        feedback.setCurrentStep(5)
        if feedback.isCanceled():
            return {}
        # Slope qsy
        alg_params = {
            'INPUT': outputs['qsy']['OUTPUT'],
            'Z_FACTOR': 1,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['qsySlope'] = processing.run('native:slope', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        # Aspect qsy
        alg_params = {
            'INPUT': outputs['qsy']['OUTPUT'],
            'Z_FACTOR': 1,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['qsyAspect'] = processing.run('native:aspect', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        # STEP 6: following from http://fatra.cnr.ncsu.edu/~hmitaso/gmslab/denix/usped.html
        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}
        feedback.pushConsoleInfo('\n~~~ Step 6: Calculated and add qsx_dx and qsy_dy ~~~\n')
        # qsx_dx = Cos((([qsx_aspect] * (-1)) + 450) * .01745) * Tan([qsx_slope] * .01745)
        alg_params = {
            'BAND_A': 1,
            'BAND_B': 1,
            'BAND_C': 1,
            'BAND_D': 1,
            'BAND_E': None,
            'BAND_F': None,
            'EXTRA': '',
            'FORMULA': 'cos(((A * -1) + 450) * .01745) * tan(B * .01745)',
            'INPUT_A': outputs['qsxAspect']['OUTPUT'],
            'INPUT_B': outputs['qsxSlope']['OUTPUT'],
            'INPUT_C': None,
            'INPUT_D': None,
            'INPUT_E': None,
            'INPUT_F': None,
            'NO_DATA': None,
            'OPTIONS': '',
            'RTYPE': 6,  # Float64
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['qsx_dx'] = processing.run('gdal:rastercalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)


        # qsy_dy =  Sin((([qsy_aspect] * (-1)) + 450) * .01745) * Tan([qsy_slope] * .01745)
        alg_params = {
            'BAND_A': 1,
            'BAND_B': 1,
            'BAND_C': 1,
            'BAND_D': 1,
            'BAND_E': None,
            'BAND_F': None,
            'EXTRA': '',
            'FORMULA': 'sin(((A * -1) + 450) * .01745) * tan(B * .01745)',
            'INPUT_A': outputs['qsyAspect']['OUTPUT'],
            'INPUT_B': outputs['qsySlope']['OUTPUT'],
            'INPUT_C': None,
            'INPUT_D': None,
            'INPUT_E': None,
            'INPUT_F': None,
            'NO_DATA': None,
            'OPTIONS': '',
            'RTYPE': 6,  # Float32
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['qsy_dy'] = processing.run('gdal:rastercalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.pushConsoleInfo('\n~~~ Final USPED Addition ~~~\n')

        # USPED = [qsx_dx] + [qsy_dy]  -> for prevailing rill erosion
        # USPED = ([qsx_dx] + [qsy_dy]) * 10.  -> for prevailing sheet erosion
        if prevailingRill: formula = 'A + B'
        else: formula = '(A + B) * 10'
        alg_params = {
            'BAND_A': 1,
            'BAND_B': 1,
            'BAND_C': 1,
            'BAND_D': 1,
            'BAND_E': None,
            'BAND_F': None,
            'EXTRA': '',
            'FORMULA': formula,
            'INPUT_A': outputs['qsx_dx']['OUTPUT'],
            'INPUT_B': outputs['qsy_dy']['OUTPUT'],
            'INPUT_C': None,
            'INPUT_D': None,
            'INPUT_E': None,
            'INPUT_F': None,
            'NO_DATA': None,
            'OPTIONS': '',
            'RTYPE': 6,  # Float64
            'OUTPUT': parameters['Usped'],
        }
        outputs['Usped'] = processing.run('gdal:rastercalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Usped'] = outputs['Usped']['OUTPUT']

        feedback.pushConsoleInfo('\n~~~ Output USPED ~~~\n')

        global outputRenamer
        outputRenamer = OutputRenamer('USPED')
        context.layerToLoadOnCompletionDetails(results['Usped']).setPostProcessor(outputRenamer)

        return results

    def name(self):
        return 'USPED'

    def displayName(self):
        return 'USPED'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return USPED()

class OutputRenamer (QgsProcessingLayerPostProcessorInterface):
    def __init__(self, layer_name):
        self.name = layer_name
        super().__init__()
        
    def postProcessLayer(self, layer, context, feedback):
        layer.setName(self.name)
