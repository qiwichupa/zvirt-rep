#!/usr/bin/env python3

# -*- coding: utf-8 -*-

import sys
import logging
import argparse
import ovirtsdk4 as sdk
import ovirtsdk4.types as types
import pandas as pd


def call_method(o, name):
    '''функция для вызова метода по имени в цикле '''
    return getattr(o, name)()


def dics_to_df(dics):
    '''Принимает массив словарей [{key1=value1, key2=value2}, {key1=value3, key2=value3},...] и возвращает pandas dataframe'''
    df = None
    for dic in dics:
        if df is None:
            df = pd.DataFrame.from_dict(dic, orient='index').transpose()
        else:
            df2 = pd.DataFrame.from_dict(dic, orient='index').transpose()
            df = pd.concat([df, df2], ignore_index = True)
    try:
        df = df.astype(str)
        # удаление лишних столбцов, содержащих нераскрытый объект типа ovirtsdk4
        string_to_exclude = 'ovirtsdk4'
        df.drop([col for col in df.columns if df[col].apply(lambda x:'ovirtsdk4' in str(x)).any()], axis=1,inplace=True)
    except Exception as e:
        print('Exception: dic_to_df: {}'.format(e))
    return(df)

def get_vm_ips(vm):
    '''Принимает объект из vms_service и возвращает все IP-адреса строкой'''
    ips=[]
    vms_service = connection.system_service().vms_service()
    vm_service = vms_service.vm_service(vm.id)
    reported_devices_service = vm_service.reported_devices_service()
    for rds in reported_devices_service.list():
        for ip in rds.ips:
            ips.append(ip.address)
    return(', '.join(ips))


def get_vm_macs(vm):
    '''Принимает объект из vms_service и возвращает все MAC-адреса строкой'''
    macs=[]
    vms_service = connection.system_service().vms_service()
    vm_service = vms_service.vm_service(vm.id)
    reported_devices_service = vm_service.reported_devices_service()
    for rds in reported_devices_service.list():
        macs.append(rds.mac.address)
    return(', '.join(macs))


def get_custom_service_df(name):
    '''Формирует массив словарей для кастомного "сервиса" и возвращает pandas dataframe для него'''
    dics = []
    if name == 'nics_service':
        print(name)
        vms_service = connection.system_service().vms_service()
        vms = vms_service.list()
        for vm in vms:
            vm_service = vms_service.vm_service(vm.id)
            nics_service = vm_service.nics_service()
            dic = {}
            for nic in nics_service.list():
                dic['vm_name'] = vm.name
                dic['nic_name'] = nic.name
                dic['nic_id'] = nic.id
                dic['nic_interface'] = nic.interface
                dic['nic_mac_address'] = nic.mac.address
                dics += [dic]
        df = dics_to_df(dics)
    return(df)


def get_custom_stat(name, obj):
    '''вспомогательная функция для get_service_df.
       Использует 1 объект стандартных сервисов (хост, вм и т.д.) и возвращает для него 1 словарь кастомных статов
       (напр. для вм: размеры, количество снапшотов, набор тегов)'''
    dic = {}
    if name == 'hosts_service':
        stats = connection.follow_link(obj.statistics)
        for stat in stats:
            dic[stat.name] = stat.values[0].datum
    if name == 'vms_service':
        vms_service = connection.system_service().vms_service()
        vm_service = vms_service.vm_service(obj.id)

        # размеры дисков ВМ
        disk_attachments_service = vm_service.disk_attachments_service()
        disk_attachments = disk_attachments_service.list()
        vm_total_size = 0
        vm_actual_size = 0
        vm_provisioned_size = 0
        for disk_attachment in disk_attachments:
            disk = connection.follow_link(disk_attachment.disk)
            #dir(disk) # вывести переменные относящиеся к диску
            vm_total_size += disk.total_size
            vm_actual_size += disk.actual_size
            vm_provisioned_size += disk.provisioned_size
        dic['vm_total_size'] = vm_total_size
        dic['vm_actual_size'] = vm_actual_size
        dic['vm_provisioned_size'] = vm_provisioned_size

        # снапшоты ВМ
        snaps_service = vm_service.snapshots_service()
        dic['vm_snapshots'] =  len(snaps_service.list()) - 1

        # теги ВМ
        tags_service = vm_service.tags_service()
        tags = ''
        for tag in tags_service.list():
            tags = '{};{}'.format(tag.name, tags)
        dic['vm_tags'] = tags

        # сетевые настройки
        dic['vm_ips'] = get_vm_ips(obj)
        dic['vm_macs'] = get_vm_macs(obj)

    return(dic)


def get_service_df(name):
    '''возвращает таблицу для стандартных сервисов, также запрашивает дополнительную статистику через get_custom_stat'''
    print(name)
    dics = []
    s = connection.system_service()
    service = call_method(s, name)
    slist = service.list()
    for obj in slist:
        objstats = vars(obj)
        customstats = get_custom_stat(name, obj)
        allstats = {**customstats, **objstats}
        dics += [allstats]
    df = dics_to_df(dics)
    return(df)

ver = '1.1.0'
parser = argparse.ArgumentParser(description='%(prog)s - reporting tool for zvirt. (v.{})'.format(ver))
parser.add_argument('-s', type=str,required=True, metavar='zvirt.dom', help='Zvirt engine fqdn or ip')
parser.add_argument('-u', type=str,required=True, metavar='user@dom', help='Zvirt engine login')
parser.add_argument('-p', type=str,required=True, metavar='pass', help='Zvirt engine password')
parser.add_argument('file', nargs=1, metavar='out.xlsx', help='path to outfile (Ex.: /tmp/zvirt_report.xlsx)')
args = parser.parse_args()


if args.file[0].endswith('.xlsx'):
    outfile=args.file[0]
else:
    outfile='{}.xlsx'.format(args.file[0])

# сервисы которые НЕ будут опрашиваться
maskedservices = [
         'affinity_labels_service'
        ,'bookmarks_service'
        ,'cluster_levels_service'
        ,'clusters_service'
        ,'connection'
        ,'cpu_profiles_service'
        ,'data_centers_service'
        ,'disk_profiles_service'
        #,'disks_service'
        ,'domains_service'
        ,'events_service'
        ,'external_host_providers_service'
        ,'external_template_imports_service'
        ,'external_vm_imports_service'
        ,'groups_service'
        #,'hosts_service'
        ,'icons_service'
        ,'instance_types_service'
        ,'image_transfers_service'
        ,'jobs_service'
        ,'katello_errata_service'
        ,'mac_pools_service'
        ,'network_filters_service'
        ,'networks_service'
        ,'openstack_image_providers_service'
        ,'openstack_network_providers_service'
        ,'openstack_volume_providers_service'
        ,'operating_systems_service'
        ,'options_service'
        ,'path'
        ,'permissions_service'
        ,'roles_service'
        ,'scheduling_policies_service'
        ,'scheduling_policy_units_service'
        ,'storage_connections_service'
        #,'storage_domains_service'
        ,'tags_service'
        ,'templates_service'
        ,'users_service'
        ,'vm_pools_service'
        #,'vms_service'
        ,'vnic_profiles_service'
        ]

# кастомные "сервисы" не из числа стандартных, с отдельной обработкой
customservices = [ 'nics_service' ]

logging.basicConfig(level=logging.WARN, filename='/tmp/zvirt-rep.log')

# параметры подключения к звирту
connection = sdk.Connection(
    url='https://{}/ovirt-engine/api'.format(args.s),
    username=args.u,
    password=args.p,
   #ca_file='ca.pem',
    insecure=True,
    debug=True,
    log=logging.getLogger(),
)

writer = pd.ExcelWriter(outfile, engine = 'xlsxwriter')

# проверка подключения, тестовый запрос
try:
    test_service = connection.system_service().tags_service()
    test_service_list = test_service.list()
except Exception as e:
    print(e)
    sys.exit(1)

system_service = connection.system_service()
srvnames = [attr for attr in dir(system_service) if not callable(getattr(system_service, attr)) and not attr.startswith("__")]
srvnames += customservices
for service in srvnames:
    if str(service).startswith('_'):
        service = str(service)[1:]
    if service not in maskedservices:
        if service not in customservices:
            try:
                wdf = get_service_df(service)
                sheetname = service[:31]
                wdf.to_excel(writer, sheet_name=sheetname)
            except Exception as e:
                print(e)
        else:
            try:
                wdf = get_custom_service_df(service)
                sheetname = service[:31]
                wdf.to_excel(writer, sheet_name=sheetname)
            except Exception as e:
                print(e)

writer.close()

connection.close()
