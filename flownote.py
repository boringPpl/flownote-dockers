#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import sys
import subprocess
import zipfile
import re

sys.tracebacklimit = None

def eprint(*args, **kwargs):
  print(*args, file=sys.stderr, **kwargs)

def oprint(*args, **kwargs):
  print(*args, file=sys.stdout, **kwargs)

def run_cmd(cmd):
  exit_code = os.system(cmd)

  if exit_code != 0:
    eprint("FLOWNOTE-ERROR ===========")
    if exit_code > 127: exit_code = 1
    sys.exit(exit_code)

  return exit_code

def format_dvc(file):
  if file.endswith(".dvc"):
    return file
  else:
    return file + ".dvc"

def zip_dir(path):
  directory = os.path.dirname(path)
  zip_name = os.path.join(directory, os.path.basename(path) + ".zip")

  with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipObj:
    for root, dirs, files in os.walk(path):
      for file in files:
        zipObj.write(os.path.join(root, file))

  return zip_name

def zip_file(path):
  directory = os.path.dirname(path)
  zip_name = os.path.join(directory, os.path.basename(path) + ".zip")

  with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipObj:
    zipObj.write(path)

  return zip_name

def unzip(files):
  if len(files) == 0: return

  for file in files:
    file_name = os.path.splitext(file)[0]
    if os.path.exists(file):
      with zipfile.ZipFile(file, 'r') as zipObj:
        base_dir = os.path.dirname(file_name)
        if base_dir != "":
          zipObj.extractall(base_dir)
        else:
          zipObj.extractall()

def init(params, flags):
  if not os.path.exists('.git'):
    run_cmd("git init")

  if not os.path.exists('.dvc'):
    run_cmd("dvc init")

def remote(params, flags):
  def check_params():
    if len(params) < 2:
      eprint("FLOWNOTE-ERROR: Missing remoteUrl")
      sys.exit(2)

  if params[0] == "metadata":
    check_params()
    run_cmd("git remote remove origin >/dev/null 2>&1 || true")
    run_cmd("git remote add origin {}".format(params[1]))
  elif params[0] == "data":
    check_params()
    run_cmd("dvc remote remove origin >/dev/null 2>&1 || true")
    run_cmd("dvc remote add -d origin {}".format(params[1]))
  elif params[0] == "list":
    run_cmd("git remote -v")
    run_cmd("dvc remote list")
  else:
    eprint("FLOWNOTE-ERROR: Unsupported Commands")
    sys.exit(2)

def add(params, flags):
  if len(params) == 0: return

  if "--zip" not in flags:
    return run_cmd("dvc add " + " ".join(map(str, params)))

  files = []

  for file_path in params:
    if os.path.isdir(file_path):
      formatted_path = re.sub(r'/$', '', file_path)
      zip_name = zip_dir(formatted_path)
      files.append(zip_name)
    else:
      zip_name = zip_file(file_path)
      files.append(zip_name)

  run_cmd("dvc add " + " ".join(files))

def remove(params, flags):
  if len(params) == 0: return
  run_cmd("dvc remove -p -f " + " ".join(map(format_dvc, params)))

def clone(params, flags):
  run_cmd("git clone " + " ".join(map(str, params)))

def commit(params, flags):
  if len(params) == 0:
    eprint("FLOWNOTE-ERROR: Missing message")
    return sys.exit(2)

  msg = params[0]
  cmd = "git ls-files --other --modified --exclude-standard | grep '.dvc\\|.gitignore' | xargs git add && git commit -m '{}'".format(msg)
  run_cmd(cmd)

def push(params, flags):
  if len(params) == 0:
    eprint("FLOWNOTE-ERROR: Missing version")
    return sys.exit(2)

  tag = params[0]
  remote = params[1] if len(params) == 2 else "origin"
  branch = params[2] if len(params) == 3 else "master"

  run_cmd("git pull -X ours --no-edit")
  run_cmd("git tag {} || true".format(tag))
  run_cmd("git push {1} {2} && git push {1} {0} && dvc push".format(tag, remote, branch))

def scan_and_unzip():
  zip_files = []
  files_str = subprocess.check_output(["git", "ls-files"])
  git_files = files_str.decode("utf-8").split("\n")

  for file in git_files:
    if file.endswith('.zip.dvc'):
      zip_files.append(os.path.splitext(file)[0])

  unzip(zip_files)

def checkout(params, flags):
  tag = params[0] if len(params) >= 1 else "master"
  dvc_remote = subprocess.check_output(["dvc", "remote", "list"])
  dvc_pull = "&& dvc pull" if dvc_remote.decode("utf-8") != '' else ''
  run_cmd("git checkout {} && git clean -fd {} && dvc checkout".format(tag, dvc_pull))
  if "--unzip" in flags: scan_and_unzip()

def pull(params, flags):
  run_cmd("git pull origin master && dvc pull")
  if "--unzip" in flags: scan_and_unzip()

def ls(params, flags):
  files_str = subprocess.check_output(["git", "ls-files"])
  git_files = files_str.decode("utf-8").split("\n")
  dvc_files = []

  for file in git_files:
    if file.endswith('.dvc'):
      dvc_files.append(os.path.splitext(file)[0])

  oprint("\n".join(dvc_files))

def version(params, flags):
  run_cmd("git describe --tags")

def versions(params, flags):
  run_cmd("git for-each-ref --sort=-taggerdate --format '%(refname:short) | %(subject)' refs/tags")

commands = {
  "init": init,
  "add": add,
  "remove": remove,
  "clone": clone,
  "commit": commit,
  "push": push,
  "checkout": checkout,
  "pull": pull,
  "ls": ls,
  "version": version,
  "versions": versions,
  "remote": remote
}

help_command = """Commands:
===============================================================
init:
  example: flownote init
remote:
  metadata:
    desc: set origin remote for git repo (metadata only)
    example: flownote remote metadata https://github.com/project
  data:
    desc: set origin remote for dvc repo (data storage)
    example: flownote remote data s3://bucket/path/to/dir
  list:
    example: flownote remote list
add:
  options: targets [targets]
  flags: --zip
  example: flownote add path/to/dir path/to/file
remove:
  options: targets [targets]
  example: flownote remove path/to/dir path/to/file
clone:
  options: url, outputDir
  example: flownote clone url outputDir
commit:
  options: message
  example: flownote commit "new version"
push:
  options: version
  example: flownote push version
checkout:
  options: version
  flags: --unzip
  example: flownote checkout version
pull:
  flags: --unzip
  example: flownote pull
ls:
  desc: list current commited files
  example: flownote ls
version:
  desc: get current version
  example: flownote version
versions:
  desc: list all the versions you pushed
  example: flownote versions
"""

if __name__ == "__main__":
  if len(sys.argv) == 1 or '--help' in sys.argv:
    print(help_command)
    sys.exit(0)

  command = os.path.basename(sys.argv[1])
  if command in commands:
    params = []
    flags = []
    for a in sys.argv[2:]:
      if a.startswith('--'):
        flags.append(a)
      else:
        params.append(a)

    commands[command](params, flags)
  else:
    eprint("Unsupported command!\nPlease use flownote --help")
    sys.exit(2)

