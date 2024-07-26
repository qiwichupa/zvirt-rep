# zvirt-rep
Скрипт генерирует выгрузку xlsx-файла с данными о системе виртуализации. Информация о хостах, ВМ, хранилищах.
```
usage: zvirt-rep.py [-h] -s zvirt.domain.loc -u user@domain -p password outfile.xlsx

zvirt-rep.py - reporting tool for zvirt

positional arguments:
  outfile.xlsx         path to outfile (Ex.: /tmp/zvirt_report.xlsx)

options:
  -h, --help           show this help message and exit
  -s zvirt.domain.loc  Zvirt engine fqdn or ip
  -u user@domain       Zvirt engine login
  -p password          Zvirt engine password
```
