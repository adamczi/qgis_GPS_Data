# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GPSdata
                                 A QGIS plugin
 Download points from your GPS
                             -------------------
        begin                : 2016-09-26
        copyright            : (C) 2016 by Adam Borczyk
        email                : ad.borczyk@gmail.com
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load GPSdata class from file GPSdata.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .gps_data import GPSdata
    return GPSdata(iface)
