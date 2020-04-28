from dnslib.server import BaseResolver, DNSRecord
from dnslib import RR, QTYPE, RCODE, CLASS
import socket


class DatabaseResolver(BaseResolver):
    def __init__(self, app, dns_manager):
        # Create application instance within this thread.
        self.app = app
        self.dns_manager = dns_manager
        self.zones = []

    def resolve(self, request, handler):
        # Create the response that we'll send back.
        reply = request.reply()

        # Try to find the requested zone.
        with self.app.app_context():
            query_log = self.dns_manager.logs_manager.create()
            query_log.source_ip = str(handler.client_address[0])
            query_log.domain = str(request.q.qname)
            query_log.type = str(QTYPE[request.q.qtype])
            query_log.rclass = str(CLASS[request.q.qclass])
            query_log.save()

            zone = self.__find_zone(request.q, query_log)
            if zone:
                reply.add_answer(zone)
            elif self.dns_manager.is_forwarding_enabled:
                # Forward query.
                reply = self.__forward(request, handler.protocol, self.dns_manager.forwarders, query_log)

        if not reply.rr:
            reply.header.rcode = RCODE.NXDOMAIN
        return reply

    def __forward(self, request, protocol, forwarders, query_log):
        reply = request.reply()

        if len(forwarders) == 0:
            # No forwarders have been configured.
            return reply

        is_tcp = (protocol == 'tcp')

        for forwarder in forwarders:
            try:
                proxy = request.send(forwarder, 53, timeout=1, tcp=is_tcp)
                reply = DNSRecord.parse(proxy)

                if reply.rr:
                    query_log.data = str(reply.q.qname)
                    query_log.forwarded = True
                    query_log.save()
            except socket.timeout:
                # Error - move to the next DNS Forwarder.
                pass

        return reply

    def __find_zone(self, query, query_log):
        zone = None

        # Split the query into an array.
        # 'something.snitch.contextis.com' will become:
        #   0 => something
        #   1 => snitch
        #   2 => contextis
        #   3 => com
        original_domain = str(query.qname)
        parts = original_domain.split('.')

        # The following loop will lookup from the longest to the shortest domain, for example:
        #   1 => something.snitch.contextis.com
        #   2 => snitch.contextis.com
        #   3 => contextis
        #   4 => com
        # Whichever it finds first, that's the one it will return and exit.
        while len(parts) > 0:
            # Join all the current items to re-create the domain.
            path = ".".join(parts)
            db_zone = self.dns_manager.find_zone(path, original_domain)
            if db_zone:
                query_log.dns_zone_id = db_zone.id
                query_log.save()

                db_record = self.dns_manager.find_record(db_zone, str(CLASS[query.qclass]), str(QTYPE[query.qtype]))
                if db_record:
                    query_log.dns_record_id = db_record.id
                    query_log.data = db_record.data
                    query_log.found = True
                    query_log.save()

                    # We found a match.
                    zone = self.__build_zone(path, db_zone, db_record)
                    break

            # Remove the first element of the array, to continue searching for a matching domain.
            parts.pop(0)

        return zone

    def __build_zone(self, domain, db_zone, db_record):
        # Create a tab separated string with the zone data.
        zone = db_zone.build_zone(db_record, domain=domain)
        # Parse the zone into a new zone object.
        new_zone = [(rr.rname, QTYPE[rr.rtype], rr) for rr in RR.fromZone(zone)]
        # Cache it.
        self.zones.append(new_zone[0])

        # Split elements.
        name, rtype, rr = new_zone[0]
        return rr
