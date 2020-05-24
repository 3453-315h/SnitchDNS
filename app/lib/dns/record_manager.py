from app.lib.models.dns import DNSRecordModel
from app.lib.dns.instances.record import DNSRecord
from twisted.names.dns import QUERY_TYPES, QUERY_CLASSES
import json
from sqlalchemy import desc, asc


class DNSRecordManager:
    def get_classes(self):
        items = list(QUERY_CLASSES.values())
        items.sort()
        return items

    def get_types(self):
        copy = QUERY_TYPES.copy()
        # Remove experimental or obsolete record types. Have to covert to list cause we delete while iterating.
        for rec, name in list(copy.items()):
            if name in ['MD', 'MF', 'MB', 'MG', 'MR', 'NULL', 'WKS', 'A6', 'MINFO', 'OPT', 'TKEY']:
                del copy[rec]

        items = list(copy.values())
        items.sort()
        return items

    def __get(self, id=None, dns_zone_id=None, ttl=None, rclass=None, type=None, data=None, active=None, order_column=None, order_by=None):
        query = DNSRecordModel.query

        if id is not None:
            query = query.filter(DNSRecordModel.id == id)

        if dns_zone_id is not None:
            query = query.filter(DNSRecordModel.dns_zone_id == dns_zone_id)

        if ttl is not None:
            query = query.filter(DNSRecordModel.ttl == ttl)

        if rclass is not None:
            query = query.filter(DNSRecordModel.rclass == rclass)

        if type is not None:
            query = query.filter(DNSRecordModel.type == type)

        if data is not None:
            query = query.filter(DNSRecordModel.data == data)

        if active is not None:
            query = query.filter(DNSRecordModel.active == active)

        if (order_column is not None) and (order_by is not None):
            order = None
            if order_column == 'id':
                order = asc(DNSRecordModel.id) if order_by == 'asc' else desc(DNSRecordModel.id)
            elif order_column == 'type':
                order = asc(DNSRecordModel.type) if order_by == 'asc' else desc(DNSRecordModel.type)

            if order is not None:
                query = query.order_by(order)

        return query.all()

    def get(self, dns_record_id, dns_zone_id=None):
        results = self.__get(id=dns_record_id, dns_zone_id=dns_zone_id)
        if len(results) == 0:
            return False

        return self.__load(results[0])

    def __load(self, item):
        return DNSRecord(item)

    def create(self):
        item = DNSRecord(DNSRecordModel())
        item.save()
        return item

    def save(self, record, dns_zone_id, ttl, rclass, type, data, active):
        record.dns_zone_id = dns_zone_id
        record.ttl = ttl
        record.rclass = rclass
        record.type = type
        record.data = json.dumps(data) if isinstance(data, dict) else data
        record.active = active

        record.save()

        return True

    def get_zone_records(self, dns_zone_id, order_column='id', order_by='asc'):
        results = self.__get(dns_zone_id=dns_zone_id, order_column=order_column, order_by=order_by)
        return self.__load_results(results)

    def can_access(self, dns_zone_id, dns_record_id, is_admin=False):
        if is_admin:
            return True

        record = self.__get(id=dns_record_id, dns_zone_id=dns_zone_id)
        return len(record) > 0

    def find(self, dns_zone_id, rclass, type, return_all=True):
        results = self.__get(dns_zone_id=dns_zone_id, rclass=rclass, type=type)
        if len(results) == 0:
            return False

        return self.__load_results(results) if return_all else self.__load(results[0])

    def count(self, dns_zone_id):
        return len(self.__get(dns_zone_id=dns_zone_id))

    def __load_results(self, results):
        records = []
        for result in results:
            records.append(self.__load(result))
        return records
