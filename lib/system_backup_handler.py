# -*- coding: utf-8 -*-
#********************************************************************
# ZYNTHIAN PROJECT: Zynthian Web Configurator
#
# System Backup Handler
#
# Copyright (C) 2017 Markus Heidt <markus@heidt-tech.com>
#
#********************************************************************
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
#
#********************************************************************

import os
import re
import logging
import base64
import json
import shutil
import tornado.web
import zipfile
from io import BytesIO
from collections import OrderedDict
import time


SYSTEM_BACKUP_ITEMS_FILE = "/zynthian/config/system_backup_items.txt"
DATA_BACKUP_ITEMS_FILE = "/zynthian/config/data_backup_items.txt"


#------------------------------------------------------------------------------
# Snapshot Config Handler
#------------------------------------------------------------------------------

class SystemBackupHandler(tornado.web.RequestHandler):

	def get_current_user(self):
		return self.get_secure_cookie("user")

	def prepare(self):
		self.genjson=False
		try:
			if self.get_query_argument("json"):
				self.genjson=True
		except:
			pass

	@tornado.web.authenticated
	def get(self, errors=None):
		config=OrderedDict([])

		config['ZYNTHIAN_SYSTEM_BACKUP_ITEMS'] = OrderedDict([])
		config['ZYNTHIAN_DATA_BACKUP_ITEMS'] = OrderedDict([])

		config['ZYNTHIAN_UPLOAD_MULTIPLE'] = False

		def addSystemBackupItem( dirname, subdirs, files ):
			config['ZYNTHIAN_SYSTEM_BACKUP_ITEMS'][dirname]=[]
			for filename in files:
				config['ZYNTHIAN_SYSTEM_BACKUP_ITEMS'][dirname].append(filename)

		def addDataBackupItem( dirname, subdirs, files ):
			config['ZYNTHIAN_DATA_BACKUP_ITEMS'][dirname]=[]
			for filename in files:
				config['ZYNTHIAN_DATA_BACKUP_ITEMS'][dirname].append(filename)

		self.walk_backup_items(addSystemBackupItem, SYSTEM_BACKUP_ITEMS_FILE)
		self.walk_backup_items(addDataBackupItem, DATA_BACKUP_ITEMS_FILE)

		if self.genjson:
			self.write(config)
		else:
			self.render("config.html", body="backup.html", config=config, title="Backup / Restore", errors=errors)

	def post(self):
		action = self.get_argument('ZYNTHIAN_BACKUP_ACTION')
		if action:
			errors = {
				'SYSTEM_BACKUP': lambda: self.do_system_backup(),
				'DATA_BACKUP': lambda: self.do_data_backup(),
			}[action]()

	def do_system_backup(self):
		self.do_backup('zynthian_system_backup',SYSTEM_BACKUP_ITEMS_FILE)

	def do_data_backup(self):
		self.do_backup('zynthian_data_backup', DATA_BACKUP_ITEMS_FILE)

	def do_backup(self, backupFileNamePrefix, backupItemsFileName):
		zipname='{0}{1}.zip'.format(backupFileNamePrefix, time.strftime("%Y%m%d-%H%M%S"))
		f=BytesIO()
		zf = zipfile.ZipFile(f, "w")
		def zip_backup_items(dirname, subdirs, files):
			zf.write(dirname)
			for filename in files:
				zf.write(os.path.join(dirname, filename))

		self.walk_backup_items(zip_backup_items, backupItemsFileName)

		zf.close()
		self.set_header('Content-Type', 'application/zip')
		self.set_header('Content-Disposition', 'attachment; filename=%s' % zipname)

		self.write(f.getvalue())
		f.close()
		self.finish()

	def get_backup_items(self, filename):
		with open(filename) as f:
			return f.read().splitlines()

	def walk_backup_items(self, worker, backupFolderFilename):
		for backupFolder in self.get_backup_items(backupFolderFilename):
			logging.info(backupFolder)
			try:
				sourceFolder = os.path.expandvars(backupFolder)
				for dirname, subdirs, files in os.walk(sourceFolder):
					worker(dirname, subdirs, files)
			except:
				pass

class RestoreProgressHandler(tornado.websocket.WebSocketHandler):

	 # the client connected
	def open(self):
		logging.info("New RestoreProgressHandler client connected")

	# the client sent the message
	def on_message(self, message):
		logging.info("restore on_message: %s" % message)
		self.do_restore(message)
		#logging.info("progress handler set for %s" % self.clientId)

	# client disconnected
	def on_close(self):
		logging.info("RestoreProgressHandler Client disconnected")

	def get_backup_items(self, filename):
		with open(filename) as f:
			return f.read().splitlines()#

	def is_valid_restore_item(self, validRestoreItems, restoreMember):
		for validRestoreItem in validRestoreItems:
			if str("/" + restoreMember).startswith(os.path.expandvars(validRestoreItem)):
				return True
		return False

	def do_restore(self, restoreFile):
		#fileinfo = self.request.files['ZYNTHIAN_RESTORE_FILE'][0]
		#restoreFile = fileinfo['filename']
		logging.debug("restoring: " + restoreFile)
		with open(restoreFile , "rb") as f:
			validRestoreItems = self.get_backup_items(SYSTEM_BACKUP_ITEMS_FILE)
			validRestoreItems += self.get_backup_items(DATA_BACKUP_ITEMS_FILE)

			with zipfile.ZipFile(f,'r') as restoreZip:
				for member in restoreZip.namelist():
					if self.is_valid_restore_item(validRestoreItems, member):
						logMessage = "restored: " + member
						restoreZip.extract(member, "/")
						logging.debug(logMessage)
						self.write_message(logMessage)
					else:
						logging.warn("restore of " + member + " not permitted")
				restoreZip.close()
			f.close()
		os.remove(restoreFile)
		self.write_message('EOCOMMAND');