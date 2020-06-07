from app.lib.base.provider import Provider
from app.lib.api.base import ApiBase
from app.lib.api.definitions.zone import Zone


class ApiZones(ApiBase):
    def all(self, user_id):
        provider = Provider()
        zones = provider.dns_zones()

        results = zones.all() if user_id is None else zones.get_user_zones(user_id)

        data = []
        for result in results:
            data.append(self.__load_zone(result))

        return self.send_valid_response(data)

    def one(self, zone_id, user_id, is_admin):
        provider = Provider()
        zones = provider.dns_zones()

        if not zones.can_access(zone_id, user_id, is_admin=is_admin):
            return self.send_access_denied_response()

        zone = zones.get(zone_id)
        if not zone:
            return self.send_access_denied_response()

        return self.send_valid_response(self.__load_zone(zone))

    def create(self, user_id, username, is_admin):
        required_fields = ['domain', 'active', 'exact_match', 'master']
        data = self.get_json(required_fields)
        if data is False:
            return self.send_error_response(
                5000,
                'Missing fields',
                'Required fields are: {0}'.format(', '.join(required_fields))
            )

        if len(data['domain']) == 0:
            return self.send_error_response(5001, 'Domain cannot be empty.', '')

        data['active'] = True if data['active'] else False
        data['exact_match'] = True if data['exact_match'] else False
        data['master'] = True if data['master'] else False

        provider = Provider()
        zones = provider.dns_zones()

        # Check for duplicate.
        base_domain = '' if is_admin else zones.get_user_base_domain(username)
        if zones.has_duplicate(0, data['domain'], base_domain):
            return self.send_error_response(5003, 'Domain already exists', '')

        zone = zones.create()
        zone = zones.save(zone, user_id, data['domain'], base_domain, data['active'], data['exact_match'], data['master'])
        if not zone:
            return self.send_error_response(5002, 'Could not create domain.', '')

        return self.one(zone.id, user_id, False)

    def update(self, zone_id, user_id, username, is_admin):
        data = self.get_json([])
        if data is False:
            return self.send_error_response(5004, 'Invalid incoming data', '')

        provider = Provider()
        zones = provider.dns_zones()

        if not zones.can_access(zone_id, user_id, is_admin=is_admin):
            return self.send_access_denied_response()

        zone = zones.get(zone_id)
        if not zone:
            return self.send_access_denied_response()

        base_domain = '' if is_admin else zones.get_user_base_domain(username)

        if ('domain' in data) and zone.master:
            data['domain'] = zone.domain
        elif 'domain' not in data:
            data['domain'] = zone.domain

        # Check for duplicates first.
        if zones.has_duplicate(zone.id, data['domain'], base_domain):
            return self.send_error_response(5003, 'Domain already exists', '')

        if 'active' in data:
            zone.active = True if data['active'] else False
        else:
            data['active'] = zone.active

        if 'exact_match' in data:
            zone.exact_match = True if data['exact_match'] else False
        else:
            data['exact_match'] = zone.exact_match

        zone = zones.save(zone, zone.user_id, data['domain'], base_domain, data['active'], data['exact_match'], zone.master)

        return self.one(zone_id, user_id, is_admin)

    def delete(self, zone_id, user_id, is_admin):
        provider = Provider()
        zones = provider.dns_zones()

        if not zones.can_access(zone_id, user_id, is_admin=is_admin):
            return self.send_access_denied_response()

        zone = zones.get(zone_id)
        if not zone:
            return self.send_access_denied_response()

        zones.delete(zone_id)
        return self.send_success_response()

    def __load_zone(self, item):
        zone = Zone()
        zone.id = item.id
        zone.user_id = item.user_id
        zone.active = int(item.active) > 0
        zone.exact_match = int(item.exact_match) > 0
        zone.master = int(item.master) > 0
        zone.domain = item.full_domain

        return zone
