# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GPSdata
                                 A QGIS plugin
 Download points from your GPS
                              -------------------
        begin                : 2016-09-26
        git sha              : $Format:%H$
        copyright            : (C) 2016 by Adam Borczyk
        email                : ad.borczyk@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, QVariant
from PyQt4.QtGui import QAction, QIcon, QFileDialog
from qgis.core import QgsPoint, QgsVectorLayer, QgsMapLayerRegistry, QgsField, QgsFeature, QgsGeometry, QgsVectorFileWriter
from qgis.gui import QgsMessageBar
# Initialize Qt resources from file resources.py
import resources
# Import the code for the dialog
from gps_data_dialog import GPSdataDialog
import os.path
import urllib, json, pynmea2, requests, re, datetime
from pynmea2.nmea import ParseError


class GPSdata:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'GPSdata_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = GPSdataDialog(self.iface.mainWindow())

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&GPS Data')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'GPSdata')
        self.toolbar.setObjectName(u'GPSdata')


        self.fileWindow()

        self.dlg.pushButton.clicked.connect(self.createShapefile)

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('GPSdata', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/GPSdata/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Get GPS data'),
            callback=self.run,
            parent=self.iface.mainWindow())


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&GPS Data'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    def fileWindow(self):
        """ Prepare window for file saving """
        self.fileDialog = QFileDialog()
        self.fileDialog.setWindowTitle('Save file')
        self.fileDialog.setAcceptMode(QFileDialog.AcceptSave)
        self.fileDialog.setFileMode(QFileDialog.AnyFile)
        self.fileDialog.setViewMode(QFileDialog.Detail)   

    def requestData(self):
        """ Get data from db """
        url = ''
        metaURL = ''

        ## Open Save File dialog and get desired path
        self.dl_path = self.fileDialog.getSaveFileName(self.fileDialog, 'Save file', filter = '*.shp')
        
        try:
            ## Run query
            response = urllib.urlopen(url)
            data = json.loads(response.read())

            ## Feature count
            metaResponse = requests.get(metaURL)
            metadata = metaResponse.json()['doc_count']

            return data, metadata

        except IOError:
            self.iface.messageBar().pushMessage("Error", "Cannot connect to the server", level=QgsMessageBar.CRITICAL, duration=5)
            self.dlg.close()
            return                 

    def createGeom(self):
        """ Prepare QgsPoint features """

        data, metadata = self.requestData()
        points = []
        attributes = []
        
        for i in range(metadata):
            item = data['rows'][i]['doc']['nmea'][0]
            attrs = {}
            try:
                parsed = pynmea2.parse(item)
                if parsed.lat and parsed.lon:
                    ## Conversion from NMEA to WGS-84
                    # mLat = re.search(r'(\d+)(\d\d)\.(\d+)?',parsed.lat)
                    # latD = int(mLat.groups()[1]+mLat.groups()[2])/60
                    # lat = float(mLat.groups()[0]+'.'+str(latD))
                    
                    # mLon = re.search(r'(\d+)(\d\d)\.(\d+)?',parsed.lon)
                    # lonD = int(mLon.groups()[1]+mLon.groups()[2])/60
                    # lon = float(mLon.groups()[0]+'.'+str(lonD))

                    lat = parsed.latitude
                    lon = parsed.longitude

                    ## Hemisphere?
                    if parsed.lat_dir == 'S':
                        lat *= -1
                    if parsed.lon_dir == 'W':
                        lon *= -1

                    ## Create feature and append to list
                    feature = QgsPoint(lon, lat)
                    points.append(feature)

                    attrs['time'] = str(parsed.timestamp)
                    attrs['lat'] = parsed.latitude
                    attrs['lon'] = parsed.longitude
                    attrs['sat'] = parsed.num_sats
                    attrs['gps_qual'] = parsed.gps_qual
                    attrs['horizontal_dil'] = parsed.horizontal_dil
                    attrs['alt'] = parsed.altitude
                    attrs['alt_u'] = parsed.altitude_units
                    attrs['geoid_sep'] = parsed.geo_sep
                    attrs['geoid_u'] = parsed.geo_sep_units
                    attrs['gps_age'] = parsed.age_gps_data
                    attrs['ref_id'] = parsed.ref_station_id

                    attributes.append(attrs)

                else:
                    print 'Empty' # Point with 0000.00000000 coords
            except ParseError:
                print 'ParseError' # Object with no attributes
        return points, attributes

    def createShapefile(self):
        """ Create shapefile """

        data, attributes = self.createGeom()

        ## Layer information
        vl = QgsVectorLayer("Point?crs=EPSG:4326", 'gps_points', "memory") 
        pr = vl.dataProvider()

        ## Add fields
        pr.addAttributes([QgsField("time", QVariant.String),
                        QgsField("latitude", QVariant.String),
                        QgsField("longitude", QVariant.String),
                        QgsField("sats", QVariant.String),
                        QgsField("gps_qual", QVariant.String),
                        QgsField("altitude", QVariant.String),
                        QgsField("alt_units", QVariant.String),
                        QgsField("horiz_dil", QVariant.String),
                        QgsField("geoid_sep", QVariant.String),
                        QgsField("geoid_unit", QVariant.String),
                        QgsField("gps_age", QVariant.String),
                        QgsField("ref_id", QVariant.String)])
        vl.updateFields()

        ## Add feature
        for i in range(len(data)):
            fet = QgsFeature()
            fet.setGeometry(QgsGeometry.fromPoint(data[i]))

            fet.setAttributes([(attributes[i]['time']),
                (attributes[i]['lat']), 
                (attributes[i]['lon']), 
                (attributes[i]['sat']),
                (attributes[i]['gps_qual']),
                (attributes[i]['alt']),
                (attributes[i]['alt_u']),
                (attributes[i]['horizontal_dil']),
                (attributes[i]['geoid_sep']),
                (attributes[i]['geoid_u']),
                (attributes[i]['gps_age']),
                (attributes[i]['ref_id'])])       

            pr.addFeatures([fet])

        ## Add map layer
        vl.updateExtents()
        QgsVectorFileWriter.writeAsVectorFormat(vl, self.dl_path+".shp", "UTF-8", None, "ESRI Shapefile")
        self.openFile()

    def openFile(self):
        """ Load file to QGIS """
        layer = self.iface.addVectorLayer(self.dl_path+'.shp', 'GPS_points', "ogr")
        if not layer:
            print "Layer failed to load!"         
        self.dlg.close()       

    def run(self):
        """ Run """
        self.dlg.show()