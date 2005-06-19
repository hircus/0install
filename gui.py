import gtk, os, gobject, sys

from zeroinstall.injector.policy import Policy
from zeroinstall.injector import download
from zeroinstall.injector.model import SafeException
from zeroinstall.injector.reader import InvalidInterface
import dialog

version = '0.7'

# Singleton Policy
policy = None

class GUIPolicy(Policy):
	window = None
	pulse = None
	monitored_downloads = None

	def __init__(self, interface, prog_args, download_only, refresh):
		Policy.__init__(self, interface)
		global policy
		assert policy is None
		policy = self
		self.monitored_downloads = []

		import mainwindow
		self.window = mainwindow.MainWindow(prog_args, download_only)
		self.window.browser.set_root(policy.get_interface(policy.root))

		if refresh:
			self.refresh_all(force = False)

	def monitor_download(self, dl):
		self.monitored_downloads.append(dl)

		error_stream = dl.start()
		def error_ready(src, cond):
			got = os.read(src.fileno(), 100)
			if not got:
				error_stream.close()
				self.monitored_downloads.remove(dl)
				if len(self.monitored_downloads) == 0:
					self.window.progress.hide()
					gobject.source_remove(self.pulse)
					self.pulse = None
				try:
					data = dl.error_stream_closed()
					self.check_signed_data(dl, data)
				except download.DownloadError, ex:
					dialog.alert(self.window,
						"Error downloading interface '%s':\n\n%s" %
						(dl.interface.uri, ex))
				except InvalidInterface, ex:
					dialog.alert(self.window,
						"Syntax error in downloaded interface '%s':\n\n%s" %
						(dl.interface.uri, ex))
				except SafeException, ex:
					dialog.alert(self.window,
						"Error updating interface '%s':\n\n%s" %
						(dl.interface.uri, ex))
				return False
			dl.error_stream_data(got)
			return True
			
		gobject.io_add_watch(error_stream,
				     gobject.IO_IN | gobject.IO_HUP,
				     error_ready)

		if self.pulse is None:
			progress = self.window.progress
			self.pulse = gobject.timeout_add(50, lambda: progress.pulse() or True)
			progress.show()
	
	def recalculate(self):
		Policy.recalculate(self)
		try:
			self.ready
		except:
			self.ready = True
			print >>sys.stderr, "Your version of the injector is very old. " \
				"Try upgrading (http://0install.net/injector.html)"
		else:
			self.window.set_response_sensitive(gtk.RESPONSE_OK, self.ready)

	def confirm_trust_keys(self, interface, sigs, iface_xml):
		import trust_box
		trust_box.confirm_trust(interface, sigs, iface_xml)

	def main(self):
		self.window.show()
		gtk.main()
	
	def get_best_source(self, impl):
		"""Return the best download source for this implementation."""
		return impl.download_sources[0]

	# XXX: Remove this. Moved to Policy.
	def refresh_all(self, force = True):
		for x in self.walk_interfaces():
			self.begin_iface_download(x, force)
	
	def abort_all_downloads(self):
		for x in self.monitored_downloads[:]:
			x.abort()

def pretty_size(size):
	if size is None:
		return '?'
	if size < 2048:
		return '%d bytes' % size
	size = float(size)
	for unit in ('Kb', 'Mb', 'Gb', 'Tb'):
		size /= 1024
		if size < 2048:
			break
	return '%.1f %s' % (size, unit)
