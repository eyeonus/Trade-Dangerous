Develop Trade-Dangerous
============================

## Setup Environment

__Linux/Mac__
```bash
git clone https://github.com/eyeonus/Trade-Dangerous
cd Trade-Dangerous
python3 -m venv venv
. venv/bin/activate
pip3 install -e .
pip3 install -r dev-requirements.txt
```

__Windows__
```powershell
git clone https://github.com/eyeonus/Trade-Dangerous
cd Trade-Dangerous
# This requires a python version >= 3.4.2
python3 -m venv venv
.\venv\Scripts\activate
pip3 install -e .
pip3 install -r dev-requirements.txt
```

## Generate Documentation

__Linux/Mac__
```bash
cd docs
make html
```

__Windows__
```powershell
cd docs
.\make.bat html
```

### Generate apidoc
```bash
cd docs
sphinx-apidoc -f -s md -o  source/ ../tradedangerous ../tradedangerous/mfd ../tradedangerous/templates ../tradedangerous/commands
```