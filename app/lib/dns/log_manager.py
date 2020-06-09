from sqlalchemy import asc, desc
from app import db
from app.lib.models.dns import DNSQueryLogModel
from app.lib.dns.instances.query_log import DNSQueryLog
import os
import csv


class DNSLogManager:
    def create(self):
        item = DNSQueryLog(DNSQueryLogModel())
        item.save()
        return item

    def __load(self, item):
        return DNSQueryLog(item)

    def __get(self, id=None, source_ip=None, domain=None, cls=None, type=None, completed=None, order_by='asc'):
        query = DNSQueryLogModel.query

        if id is not None:
            query = query.filter(DNSQueryLogModel.id == id)

        if source_ip is not None:
            query = query.filter(DNSQueryLogModel.source_ip == source_ip)

        if domain is not None:
            query = query.filter(DNSQueryLogModel.domain == domain)

        if cls is not None:
            query = query.filter(DNSQueryLogModel.cls == cls)

        if type is not None:
            query = query.filter(DNSQueryLogModel.type == type)

        if completed is not None:
            query = query.filter(DNSQueryLogModel.completed == completed)

        order = asc(DNSQueryLogModel.id) if order_by == 'asc' else desc(DNSQueryLogModel.id)
        query = query.order_by(order)

        return query.all()

    def find(self, domain, cls, type, completed, source_ip):
        results = self.__get(domain=domain, cls=cls, type=type, completed=completed, source_ip=source_ip)
        return self.__load(results[0]) if results else None

    def __prepare_path(self, save_as, overwrite, create_path):
        if save_as != os.path.realpath(save_as):
            raise Exception("Coding error: Passed path must be absolute.")

        # Check if the path exists.
        path = os.path.dirname(save_as)
        if not os.path.isdir(path):
            if not create_path:
                return False
            os.makedirs(path, exist_ok=True)
            if not os.path.isdir(path):
                # If it still doesn't exist.
                return False

        # Check if the file exists.
        if os.path.isfile(save_as):
            if not overwrite:
                return False

            os.remove(save_as)
            if os.path.isfile(save_as):
                # If the file still exists.
                return False

        return True

    def save_results_csv(self, rows, save_as, overwrite=False, create_path=False):
        if not self.__prepare_path(save_as, overwrite, create_path):
            return False

        header = [
            'id',
            'domain',
            'source_ip',
            'class',
            'type',
            'date',
            'forwarded',
            'matched'
        ]
        with open(save_as, 'w') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(header)

            for row in rows:
                line = [
                    row.id,
                    row.domain,
                    row.source_ip,
                    row.cls,
                    row.type,
                    row.created_at,
                    '1' if row.forwarded else '0',
                    '1' if row.found else '0'
                ]
                writer.writerow(line)

        return os.path.isfile(save_as)

    def get_last_log_id(self, dns_zone_id):
        sql = "SELECT COALESCE(MAX(id), 0) AS max_id FROM dns_query_log WHERE dns_zone_id = :id"
        result = db.session.execute(sql, {'id': dns_zone_id}).fetchone()
        return int(result['max_id'])
