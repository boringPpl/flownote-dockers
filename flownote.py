#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import sys
import subprocess
import zipfile
import re
import base64
import json
import urllib2
import argparse

sys.tracebacklimit = None
FLOWNOTE_URL = os.environ.get("FLOWNOTE_URL", "https://api.flownote.ai/apollo")
FLOWNOTE_TOKEN = os.environ.get("FLOWNOTE_TOKEN")
FLOWNOTE_DATASOURCE_CRED_PATH = "/flownote/datasources"

def eprint(*args, **kwargs):
  print(*args, file=sys.stderr, **kwargs)

def oprint(*args, **kwargs):
  print(*args, file=sys.stdout, **kwargs)

def run_cmd(cmd, err = "Unknown"):
  exit_code = os.system(cmd)

  if exit_code != 0:
    eprint("FLOWNOTE-ERROR: {}\n".format(err))
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

  with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zipObj:
    for root, dirs, files in os.walk(path):
      for file in files:
        zipObj.write(os.path.join(root, file))

  return zip_name

def zip_file(path):
  directory = os.path.dirname(path)
  zip_name = os.path.join(directory, os.path.basename(path) + ".zip")

  with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zipObj:
    zipObj.write(path)

  return zip_name

def unzip(files):
  if len(files) == 0: return

  for file in files:
    file_name = os.path.splitext(file)[0]
    if os.path.exists(file):
      with zipfile.ZipFile(file, "r") as zipObj:
        base_dir = os.path.dirname(file_name)
        if base_dir != "":
          zipObj.extractall(base_dir)
        else:
          zipObj.extractall()

def init(params):
  if not os.path.exists(".git"):
    run_cmd("git init", "Unable to initialize Git")

  if not os.path.exists(".dvc"):
    run_cmd("dvc init", "Unable to initialize DVC")

def remote(params):
  print(params)
  def check_params():
    if not params.url:
      eprint("FLOWNOTE-ERROR: Missing remoteUrl\n")
      sys.exit(2)

  if params.action == "metadata":
    check_params()
    run_cmd("git remote remove origin >/dev/null 2>&1 || true")
    run_cmd("git remote add origin {}".format(params.url))
  elif params.action == "data":
    check_params()
    run_cmd("dvc remote remove origin >/dev/null 2>&1 || true")
    run_cmd("dvc remote add -d origin {}".format(params.url))
  elif params.action == "list":
    run_cmd("git remote -v")
    run_cmd("dvc remote list")

def add(params):
  add_cmd = "dvc add " + " ".join(map(str, params.targets))

  if not params.zip:
    return run_cmd(add_cmd, "Unable to add files")

  files = []

  for file_path in params.targets:
    if os.path.isdir(file_path):
      formatted_path = re.sub(r"/$", "", file_path)
      zip_name = zip_dir(formatted_path)
      files.append(zip_name)
    else:
      zip_name = zip_file(file_path)
      files.append(zip_name)

  return run_cmd(add_cmd, "Unable to add files")

def remove(params):
  run_cmd("dvc remove -p -f " + " ".join(map(format_dvc, params.targets)), "Unable to remove files")

def clone(params):
  outputDir = params.dir if params.dir else ""
  run_cmd(" ".join(["git clone", params.url, outputDir]), "Unable to clone repo")

def commit(params):
  cmd = "git ls-files --other --modified --exclude-standard | grep '.dvc\\|.gitignore' | xargs git add && git commit -m '{}'".format(params.message)
  run_cmd(cmd, "Unable to commit")

def push(params):
  if not params.skip_merge:
    run_cmd("git pull -X ours --no-edit --tags origin master", "Unable to merge automatically")

  try:
    tag_str = subprocess.check_output(["git", "for-each-ref", "--sort=-taggerdate", "--format", "%(refname:short)", "refs/tags", "--count=1"])
    tag = int(tag_str.rstrip()) + 1
  except subprocess.CalledProcessError:
    tag = 1
  except ValueError:
    tag = 1

  message = params.version or tag
  run_cmd("git tag -a {} -m '{}' || true".format(tag, message))
  run_cmd("git push origin HEAD:master && git push origin {} && dvc push".format(tag), "Unable to push")

def scan_and_unzip():
  zip_files = []
  files_str = subprocess.check_output(["git", "ls-files"])
  git_files = files_str.decode("utf-8").split("\n")

  for file in git_files:
    if file.endswith(".zip.dvc"):
      zip_files.append(os.path.splitext(file)[0])

  unzip(zip_files)

def checkout(params):
  print(params)
  tag = params.version or "master"

  run_cmd("git checkout {} && git clean -fd".format(tag), "Unable to checkout")
  os.system("dvc pull")
  run_cmd("dvc checkout", "Unable to checkout")
  if params.unzip: scan_and_unzip()

def pull(params):
  run_cmd("git pull --tags origin master && dvc pull", "Unable to pull")
  if params.unzip: scan_and_unzip()

def version(params):
  run_cmd("git describe --tags", "Unable to get current version")

def versions(params):
  run_cmd("git for-each-ref --sort=-taggerdate --format '%(refname:short) | %(subject)' refs/tags", "Unable to list versions")

def request(query, variables):
  req = urllib2.Request(FLOWNOTE_URL)
  req.add_header("Content-Type", "application/json")
  req.add_header("KernelToken", FLOWNOTE_TOKEN)

  response = urllib2.urlopen(req, json.dumps({
    "query": query,
    "variables": variables,
  }))
  json_response = json.loads(response.read())
  errors = json_response.get("errors")

  if errors:
    eprint("FLOWNOTE-ERROR: {}\n".format(errors[0]["message"]))
    sys.exit(2)
  return json_response["data"]

def request_datasets(dataset_ids):
  query = """
    query($filter: ContentListFilterInputType) {
      datasetsPaginate(filter: $filter) {
        data {
          id
          slug
          downloadOption {
            url
            protocol
          }
        }
      }
    }
  """
  variables = { "filter": { "ids": dataset_ids } }
  response = request(query, variables)
  return response["datasetsPaginate"]["data"]

def build_dataset_dir(dataset):
  return "/flownote/input/{}".format(dataset["slug"])

def download(ds):
  downloadOption = ds["downloadOption"]
  dataset_dir = build_dataset_dir(ds)
  dataset_file = "{}/{}.zip".format(dataset_dir, ds["id"])

  if downloadOption["protocol"] == "HTTP":
    run_cmd("mkdir -p {} && wget '{}' -O '{}'".format(dataset_dir, downloadOption["url"], dataset_file))
    unzip([dataset_file])
    os.system("rm -rf {}".format(dataset_file))
  elif downloadOption["protocol"] == "GIT":
    clone(argparse.Namespace(url=downloadOption["url"], dir=dataset_dir))
    os.system("cd {} && dvc pull".format(dataset_dir))
    os.system("cd -")
  else:
    eprint("FLOWNOTE-ERROR: Invalid Protocol\n")
    sys.exit(2)

  return dataset_dir

def pull_datasets(dataset_ids):
  dss = request_datasets(dataset_ids)

  if len(dss) == 0:
    eprint("FLOWNOTE-ERROR: Dataset Not Found\n")
    sys.exit(2)

  dirs = []
  for ds in dss:
    url = ds["downloadOption"].get("url")
    if url: dirs.append(download(ds))

  oprint(",".join(dirs))
  return dirs

def datasets(params):
  return pull_datasets(params.ids)

def find_datasource_by_id(datasource_id):
  query = '''
    query datasourceById($id: ID!) {
      datasource(id: $id) {
        id
        title
        type
        defaultUser
        defaultPassword
        databaseName
        secretName
        host
        port
        bigQueryProject
        bigQueryDataset
      }
    }
  '''
  variables = {"id": datasource_id}
  response = request(query, variables)

  return response["datasource"]

datasource_connection_protocol = {
  # "PRESTO": "presto",
  "POSTGRESQL": "postgresql+psycopg2",
  "MYSQL": "mysql+pymysql",
  "REDSHIFT": "redshift+psycopg2",
  "BIGQUERY": "bigquery",
  "ORACLE": "oracle"
}

def get_destination(user, password, host, port):
  auth = ''
  if user:
    if password:
      auth = "{}:{}".format(user, password)
    else:
      auth = user
  location = "{}:{}".format(host, port) if port else host
  return "{}@{}".format(auth, location) if auth else location

def generate_datasource_connection_string(datasource):
  datasource_type = datasource.get('type')
  if not datasource_type in datasource_connection_protocol:
    eprint("FLOWNOTE-ERROR: unsupported datasource type\n")
    sys.exit(2)
  protocol = datasource_connection_protocol.get(datasource_type)
  bigQueryProject = datasource.get('bigQueryProject')
  if (datasource_type == 'BIGQUERY'):
    return "{}://{}".format(protocol, bigQueryProject)
  database_name = datasource.get('databaseName')
  host = datasource.get('host')
  port = datasource.get('port')
  user = datasource.get('defaultUser')
  password = datasource.get('defaultPassword')
  datasource_id = datasource.get('id')
  credential_path = os.path.join(FLOWNOTE_DATASOURCE_CRED_PATH, datasource_id)

  # load custom credential
  # custom credential is injected by k8s
  if os.path.exists(credential_path):
    with open(credential_path) as f:
      custom_credential = json.load(f)
      if custom_credential.get('user'):
        user = custom_credential.get('user')
      if custom_credential.get('password'):
        password = custom_credential.get('password')

  destination = get_destination(user, password, host, port)
  return "{}://{}/{}".format(protocol, destination, database_name)

# TODO: will support list all later
def datasources(params):
  datasource = find_datasource_by_id(params.id)
  result = ''

  if params.cmd == 'desc':
    result = json.dumps(datasource, indent=2)

  if params.cmd == 'connection_string':
    result = generate_datasource_connection_string(datasource)

  oprint(result)
  return sys.exit(0)

def request_notebook(nb_id, path):
  query = """
    mutation($id: ID!, $uniqPath: String) {
      topicSnapshotCreate(id: $id, uniqPath: $uniqPath)
    }
  """
  variables = { "id": nb_id, "uniqPath": path }
  response = request(query, variables)

  return response["topicSnapshotCreate"]

def request_output(nb_id, path):
  query = """
    mutation($id: ID!, $uniqPath: String!) {
      topicOutputCreate(id: $id, uniqPath: $uniqPath)
    }
  """
  variables = { "id": nb_id, "uniqPath": path }
  response = request(query, variables)

  return response["topicOutputCreate"]

def upload_output(nb_id, path, output):
  url = request_output(nb_id, output)
  run_cmd("wget --header='Content-Type: text/html' --method PUT --body-file={} '{}'".format(path, url))

def run_notebook(params):
  url = request_notebook(params.id, params.snapshot)
  file_name = "{}.ipynb".format(params.id)
  html_file_name = "{}.html".format(params.id)

  run_cmd("wget '{0}' -O '{1}' && jupyter nbconvert --no-input --execute '{1}'".format(url, file_name))

  if (params.output):
    upload_output(params.id, "./{}".format(html_file_name), params.output)

def notebook(params):
  return run_notebook(params)

def init_parser(args):
  parser = argparse.ArgumentParser(description="Initialize dataset", usage="%(prog)s init")
  return parser.parse_args(args)

def remote_parser(args):
  parser = argparse.ArgumentParser(description="List/Set dataset remote")
  parser.add_argument("action", type=str, help="metadata/data/list", choices=["metadata", "data", "list"])
  parser.add_argument("--url", action="store", type=str, help="remote url")
  return parser.parse_args(args)

def add_parser(args):
  parser = argparse.ArgumentParser(description="Add file/folder to dataset", usage="%(prog)s add [-h] [--zip] targets [targets ...]")
  parser.add_argument("targets", type=str, nargs="+", help="file path")
  parser.add_argument("--zip", action="store_true", default=False, help="zip file/folder before add")
  return parser.parse_args(args)

def remove_parser(args):
  parser = argparse.ArgumentParser(description="Remove file/folder from dataset", usage="%(prog)s remove [-h] targets [targets ...]")
  parser.add_argument("targets", type=str, nargs="+", help="file path")
  return parser.parse_args(args)

def clone_parser(args):
  parser = argparse.ArgumentParser(description="Clone dataset repo", usage="%(prog)s clone [-h] url [dir]")
  parser.add_argument("url", type=str, help="repo url")
  parser.add_argument("dir", type=str, nargs="?", help="output dir")
  return parser.parse_args(args)

def commit_parser(args):
  parser = argparse.ArgumentParser(description="Commit dataset changes", usage="%(prog)s commit [-h] message")
  parser.add_argument("message", type=str, help="changes description")
  return parser.parse_args(args)

def push_parser(args):
  parser = argparse.ArgumentParser(description="Push dataset changes", usage="%(prog)s push [-h] [--skip-merge] [version]")
  parser.add_argument("version", type=str, nargs="?", help="dataset version")
  parser.add_argument("--skip-merge", action="store_true", default=False, help="fetch & merge before push")
  return parser.parse_args(args)

def checkout_parser(args):
  parser = argparse.ArgumentParser(description="Checkout dataset version", usage="%(prog)s checkout [-h] [--unzip] [version]")
  parser.add_argument("version", type=str, nargs="?", help="dataset version")
  parser.add_argument("--unzip", action="store_true", default=False, help="unzip after checkout")
  return parser.parse_args(args)

def pull_parser(args):
  parser = argparse.ArgumentParser(description="Pull dataset", usage="%(prog)s pull [-h] [--unzip]")
  parser.add_argument("--unzip", action="store_true", default=False, help="unzip after pull")
  return parser.parse_args(args)

def version_parser(args):
  parser = argparse.ArgumentParser(description="Get current dataset version", usage="%(prog)s version [-h]")
  return parser.parse_args(args)

def versions_parser(args):
  parser = argparse.ArgumentParser(description="List dataset versions", usage="%(prog)s versions [-h]")
  return parser.parse_args(args)

def datasets_parser(args):
  parser = argparse.ArgumentParser(description="Pull flownote datasets", usage="%(prog)s [-h] datasets {pull} ids [ids ...]")
  parser.add_argument("action", type=str, choices=['pull'])
  parser.add_argument("ids", type=str, nargs="+", help="flownote dataset id")
  return parser.parse_args(args)

def notebook_parser(args):
  parser = argparse.ArgumentParser(description="Run flownote notebook", usage="%(prog)s [-h] notebook {run} id")
  parser.add_argument("action", type=str, choices=['run'])
  parser.add_argument("id", type=str, help="flownote dataset id")
  parser.add_argument("--snapshot", type=str, help="snapshot path")
  parser.add_argument("--output", type=str, help="output path")
  return parser.parse_args(args)

def datasources_parser(args):
  parser = argparse.ArgumentParser(description="Get flownote datasources information", usage="%(prog)s [-h] datasources {desc,connection_string} id")
  parser.add_argument("cmd", type=str, choices=['desc', 'connection_string'])
  parser.add_argument("id", type=str, help="flownote datasource id")
  return parser.parse_args(args)

parsers = {
  "init": init_parser,
  "add": add_parser,
  "remove": remove_parser,
  "clone": clone_parser,
  "commit": commit_parser,
  "push": push_parser,
  "checkout": checkout_parser,
  "pull": pull_parser,
  "version": version_parser,
  "versions": versions_parser,
  "remote": remote_parser,
  "datasets": datasets_parser,
  "notebook": notebook_parser,
  "datasources": datasources_parser,
}

commands = {
  # Manipulate Dataset
  "init": init,
  "add": add,
  "remove": remove,
  "clone": clone,
  "commit": commit,
  "push": push,
  "checkout": checkout,
  "pull": pull,
  "version": version,
  "versions": versions,
  "remote": remote,
  # Other
  "datasets": datasets,
  "notebook": notebook,
  "datasources": datasources,
}

help_command = """usage: flownote [-h] command

List of commands:

manipulate dataset
  init         Initialize dataset
  remote       List/Set dataset remote
  add          Add file/folder to dataset
  remove       Remove file/folder from dataset
  clone        Clone dataset repo
  commit       Commit dataset changes
  push         Push dataset changes
  checkout     Checkout dataset version
  pull         Pull dataset
  version      Get current dataset version
  versions     List dataset versions

flownote commands (require flownote token)
  datasets     Pull flownote datasets
  notebook     Run flownote notebook
  datasources  Get flownote datasources information

optional arguments:
  -h, --help  show this help message and exit
"""

if __name__ == "__main__":
  if len(sys.argv) == 1 or (len(sys.argv) >= 2 and sys.argv[1] in ["-h", "--help"]):
    oprint(help_command)
    sys.exit(0)

  command = os.path.basename(sys.argv[1])
  if command not in commands:
    oprint(help_command)
    sys.exit(0)

  parser = parsers.get(command)
  args = parser(sys.argv[2:])
  commands[command](args)
