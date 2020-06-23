import re
import os
import csv
from app.lib.models.dns import DNSZoneModel
from app.lib.dns.instances.zone import DNSZone
from app.lib.dns.helpers.shared import SharedHelper
from sqlalchemy import func


class DNSZoneManager(SharedHelper):
    def __init__(self, settings, dns_records, users, notifications, dns_logs, dns_restrictions):
        self.settings = settings
        self.dns_records = dns_records
        self.users = users
        self.notifications = notifications
        self.dns_logs = dns_logs
        self.dns_restrictions = dns_restrictions

    def __get(self, id=None, user_id=None, domain=None, base_domain=None, full_domain=None, active=None,
              exact_match=None, master=None, order_by='id'):
        query = DNSZoneModel.query

        if id is not None:
            query = query.filter(DNSZoneModel.id == id)

        if domain is not None:
            query = query.filter(func.lower(DNSZoneModel.domain) == domain.lower())

        if active is not None:
            query = query.filter(DNSZoneModel.active == active)

        if exact_match is not None:
            query = query.filter(DNSZoneModel.exact_match == exact_match)

        if user_id is not None:
            query = query.filter(DNSZoneModel.user_id == user_id)

        if full_domain is not None:
            query = query.filter(func.lower(DNSZoneModel.full_domain) == full_domain.lower())

        if base_domain is not None:
            query = query.filter(func.lower(DNSZoneModel.base_domain) == base_domain.lower())

        if master is not None:
            query = query.filter(DNSZoneModel.master == master)

        if order_by == 'user_id':
            query = query.order_by(DNSZoneModel.user_id)
        elif order_by == 'full_domain':
            query = query.order_by(DNSZoneModel.full_domain)
        else:
            query = query.order_by(DNSZoneModel.id)

        return query.all()

    def get(self, dns_zone_id, user_id=None):
        results = self.__get(id=dns_zone_id, user_id=user_id)
        if len(results) == 0:
            return False

        return self.__load(results[0])

    def delete(self, dns_zone_id):
        zone = self.get(dns_zone_id)
        if not zone:
            return False

        records = self.dns_records.get_zone_records(zone.id)
        for record in records:
            self.dns_records.delete(record)

        restrictions = self.dns_restrictions.get_zone_restrictions(zone.id).all()
        for restriction in restrictions:
            restriction.delete()

        subscriptions = zone.notifications.all()
        for name, subscription in subscriptions.items():
            self.notifications.logs.delete(subscription_id=subscription.id)
            subscription.delete()

        self.dns_logs.delete(dns_zone_id=zone.id)

        zone.delete()

        return True

    def __load(self, item):
        zone = DNSZone(item)
        zone.record_count = self.dns_records.count(dns_zone_id=zone.id)
        zone.username = self.users.get_user(zone.user_id).username
        zone.notifications = self.notifications.get_zone_subscriptions(zone.id)
        zone.match_count = self.dns_logs.count(dns_zone_id=zone.id)
        zone.restrictions = self.dns_restrictions.get_zone_restrictions(zone.id)
        return zone

    def create(self):
        item = DNSZone(DNSZoneModel())
        item.save()
        return item

    def save(self, zone, user_id, domain, base_domain, active, exact_match, master, forwarding):
        zone.user_id = user_id
        zone.domain = self.__fix_domain(domain)
        zone.base_domain = self.__fix_domain(base_domain)
        zone.full_domain = zone.domain + zone.base_domain
        zone.active = active
        zone.exact_match = exact_match
        zone.master = master
        zone.forwarding = forwarding
        zone.save()

        return zone

    def __fix_domain(self, domain):
        return domain.rstrip('.')

    def all(self):
        results = self.__get()

        zones = []
        for result in results:
            zones.append(self.__load(result))

        return zones

    def get_user_zones(self, user_id, order_by='id'):
        results = self.__get(user_id=user_id, order_by=order_by)

        zones = []
        for result in results:
            zones.append(self.__load(result))

        return zones

    def find(self, full_domain, user_id=None):
        results = self.__get(full_domain=full_domain, user_id=user_id)
        if len(results) == 0:
            return False

        return self.__load(results[0])

    @property
    def base_domain(self):
        return self.settings.get('dns_base_domain', '')

    def get_user_base_domain(self, username):
        dns_base_domain = self.__fix_domain(self.base_domain).lstrip('.')
        # Keep only letters, digits, underscore.
        username = self.__clean_username(username)
        return '.' + username + '.' + dns_base_domain

    def get_base_domain(self, is_admin, username):
        return '' if is_admin else self.get_user_base_domain(username)

    def __clean_username(self, username):
        return re.sub(r'\W+', '', username)

    def has_duplicate(self, dns_zone_id, domain, base_domain):
        return DNSZoneModel.query.filter(
            DNSZoneModel.id != dns_zone_id,
            DNSZoneModel.domain == domain,
            DNSZoneModel.base_domain == base_domain
        ).count() > 0

    def can_access(self, dns_zone_id, user_id):
        if self.users.is_admin(user_id):
            return True
        return len(self.__get(id=dns_zone_id, user_id=user_id)) > 0

    def create_user_base_zone(self, user):
        if len(self.base_domain) == 0:
            return False

        zone = self.create()
        return self.save(zone, user.id, self.__clean_username(user.username), '.' + self.base_domain, True, False, True, False)

    def count(self, user_id=None):
        return len(self.__get(user_id=user_id))

    def exists(self, dns_zone_id=None, full_domain=None):
        return len(self.__get(id=dns_zone_id, full_domain=full_domain)) > 0

    def new(self, domain, active, exact_match, forwarding, user_id, master=False):
        errors = []

        if len(domain) == 0:
            errors.append('Invalid domain')
            return errors

        user = self.users.get_user(user_id)
        if not user:
            errors.append('Could not load user')
            return errors

        base_domain = self.get_base_domain(user.admin, user.username)
        if self.has_duplicate(0, domain, base_domain):
            errors.append('This domain already exists.')
            return errors

        zone = self.create()
        if not zone:
            errors.append('Could not get zone')
            return errors

        zone = self.save(zone, user.id, domain, base_domain, active, exact_match, master, forwarding)
        if not zone:
            errors.append('Could not save zone')
            return errors

        return zone

    def update(self, zone_id, domain, active, exact_match, forwarding, user_id, master=False):
        errors = []

        if len(domain) == 0:
            errors.append('Invalid domain')
            return errors

        zone = self.get(zone_id, user_id=user_id)
        if not zone:
            errors.append('Invalid zone')
            return errors

        user = self.users.get_user(user_id)
        if not user:
            errors.append('Could not load user')
            return errors

        base_domain = self.get_base_domain(user.admin, user.username)
        if self.has_duplicate(zone.id, domain, base_domain):
            errors.append('This domain already exists.')
            return errors

        zone = self.save(zone, user.id, domain, base_domain, active, exact_match, master, forwarding)
        return zone

    def export(self, user_id, save_as, overwrite=False, create_path=False):
        if not self._prepare_path(save_as, overwrite, create_path):
            return False

        zones = self.get_user_zones(user_id, order_by='full_domain')

        header = [
            'type',
            'domain',
            'd_active',
            'd_exact_match',
            'd_forwarding',
            'd_master',
            'r_id',
            'r_ttl',
            'r_cls',
            'r_type',
            'r_active',
            'r_data'
        ]
        with open(save_as, 'w') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(header)

            for zone in zones:
                # Write the zone.
                zone_line = [
                    'zone',
                    self._sanitise_csv_value(zone.full_domain),
                    '1' if zone.active else '0',
                    '1' if zone.exact_match else '0',
                    '1' if zone.forwarding else '0',
                    '1' if zone.master else '0'
                ]
                writer.writerow(zone_line)

                # Write the records.
                records = self.dns_records.get_zone_records(zone.id, order_column='type')
                for record in records:
                    properties = []
                    for name, value in record.properties().items():
                        properties.append("{0}={1}".format(name, value))

                    record_line = [
                        'record',
                        self._sanitise_csv_value(zone.full_domain),
                        '',
                        '',
                        '',
                        '',
                        record.id,
                        record.ttl,
                        record.cls,
                        record.type,
                        '1' if record.active else '0',
                        "\n".join(properties)
                    ]
                    writer.writerow(record_line)

        return os.path.isfile(save_as)
