# -*- coding: utf-8 -*-

"""
/***************************************************************************
ErosionFlow
 A QGIS plugin with QGIS : 32214
 Provides Basic erosion processing algorithms, such as RUSLE AND USPED
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2023-03-28
        copyright            : (C) 2023 by Michael Tuck
        email                : contact@michaeltuck.com
        MIT LICENCE                                                         
 ***************************************************************************/
"""

__author__ = 'Michael Tuck'
__date__ = '2023-03-28'
__copyright__ = '(C) 2023 by Michael Tuck'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from qgis.core import QgsProcessingProvider
from .erosion_flow_LS import LSarea
from .erosion_flow_RUSLE3D import RUSLE
from .erosion_flow_USPED import USPED


class ErosionFlowProvider(QgsProcessingProvider):

    def __init__(self):
        """
        Default constructor.
        """
        QgsProcessingProvider.__init__(self)

    def unload(self):
        """
        Unloads the provider. Any tear-down steps required by the provider
        should be implemented here.
        """
        pass

    def loadAlgorithms(self):
        """
        Loads all algorithms belonging to this provider.
        """
        self.addAlgorithm(LSarea())
        self.addAlgorithm(RUSLE())
        self.addAlgorithm(USPED())

    def id(self):
        """
        Returns the unique provider id, used for identifying the provider. This
        string should be a unique, short, character only string, eg "qgis" or
        "gdal". This string should not be localised.
        """
        return 'ErosionFlow'

    def name(self):
        """
        Returns the provider name, which is used to describe the provider
        within the GUI.

        This string should be short (e.g. "Lastools") and localised.
        """
        return self.tr('ErosionFlow')

    def icon(self):
        """
        Should return a QIcon which is used for your provider inside
        the Processing toolbox.
        """
        return QgsProcessingProvider.icon(self)

    def longName(self):
        """
        Returns the a longer version of the provider name, which can include
        extra details such as version numbers. E.g. "Lastools LIDAR tools
        (version 2.2.1)". This string should be localised. The default
        implementation returns the same string as name().
        """
        return self.name()
