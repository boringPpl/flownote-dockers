from jupyter_core.paths import jupyter_data_dir
import subprocess
import os
import errno
import stat

c = get_config()
c.NotebookApp.ip = '0.0.0.0'
c.NotebookApp.port = 8888
c.NotebookApp.open_browser = False
c.NotebookApp.allow_origin = '*'
c.NotebookApp.token = ''
c.NotebookApp.disable_check_xsrf = True

# https://github.com/jupyter/notebook/issues/3130
c.FileContentsManager.delete_to_trash = False