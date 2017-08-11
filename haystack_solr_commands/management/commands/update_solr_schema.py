from __future__ import print_function
from __future__ import unicode_literals
import sys

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand
from django.template import loader, Context

from haystack.backends.solr_backend import SolrSearchBackend
from haystack import constants


class Command(BaseCommand):
    help = """Generates a Solr schema that reflects the indexes.
    A modified version of the official build_solr_schema support
    both Solr 5.0.0 and 4.2.10 (if using parameter -f or -s)
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '-f', '--filename',
            action='store',
            dest='filename',
            default=False,
            help='For Solr before 5.0.0. If provided, directs output\
            to a XML schema.'
        ),
        parser.add_argument(
            '-s', '--stdout',
            action='store_true',
            dest='stdout',
            default=False,
            help='For Solr before 5.0.0, print on stdout the schema.xml'
        )
        parser.add_argument(
            '-u', '--using',
            action='store',
            dest='using',
            default=constants.DEFAULT_ALIAS,
            help='If provided, chooses a connection to work with.'
        )

    def handle(self, **options):
        """Generates a Solr schema that reflects the indexes."""
        from haystack import connections

        using = options.get('using')
        backend = connections[using].get_backend()

        if not isinstance(backend, SolrSearchBackend):
            raise ImproperlyConfigured("'%s' isn't configured as a\
                                       SolrEngine)."
                                       % backend.connection_alias)

        if options.get('filename') or options.get('stdout'):
            schema_xml = self.build_template(using=using)
            if options.get('filename'):
                self.write_file(options.get('filename'), schema_xml)
            else:
                self.print_schema(schema_xml)
            return

        content_field_name, fields = backend.build_schema(connections[using]
                                                          .get_unified_index()
                                                          .all_searchfields())

        django_fields = [
            dict(name=constants.ID, type="string", indexed="true",
                 stored="true", multiValued="false", required="true"),
            dict(name=constants.DJANGO_CT, type="string", indexed="true",
                 stored="true", multiValued="false"),
            dict(name=constants.DJANGO_ID, type="string", indexed="true",
                 stored="true", multiValued="false"),
            dict(name="_version_", type="long", indexed="true", stored="true"),
        ]

        admin = backend.get_schema_admin()
        for field in fields + django_fields:
            resp = admin.add_field(field)
            self.log(field, resp, backend)

    def build_context(self, using):
        from haystack import connections
        backend = connections[using].get_backend()

        if not isinstance(backend, SolrSearchBackend):
            raise ImproperlyConfigured("'%s' isn't configured as a\
                                       SolrEngine)."
                                       % backend.connection_alias)

        content_field_name, fields = backend.build_schema(connections[using]
                                                          .get_unified_index()
                                                          .all_searchfields())
        return Context({
            'content_field_name': content_field_name,
            'fields': fields,
            'default_operator': constants.DEFAULT_OPERATOR,
            'ID': constants.ID,
            'DJANGO_CT': constants.DJANGO_CT,
            'DJANGO_ID': constants.DJANGO_ID,
        })

    def build_template(self, using):
        t = loader.get_template('search_configuration/solr.xml')
        c = self.build_context(using=using)
        return t.render(c)

    def write_file(self, filename, schema_xml):
        schema_file = open(filename, 'w')
        schema_file.write(schema_xml)
        schema_file.close()

    def print_schema(self, schema_xml):
        sys.stderr.write("\n")
        sys.stderr.write("\n")
        sys.stderr.write("\n")
        sys.stderr.write("Save the following output to 'schema.xml' and place\
                         it in your Solr configuration directory.\n")
        sys.stderr.write("-------------------------------------------------------\
                         -------------------------------------\n")
        sys.stderr.write("\n")
        print(schema_xml)

    def log(self, field, response, backend):
        try:
            message = response.json()
        except ValueError:
            raise Exception('unable to decode Solr API, are sure you started\
                            Solr and created the configured Core (%s) ?'
                            % backend.conn.url)

        if 'errors' in message:
            sys.stdout.write("%s.\n" % [" ".join(err.get('errorMessages'))
                             for err in message['errors']])
        elif 'responseHeader' in message and 'status' in message['responseHeader']:
            sys.stdout.write("Successfully created the field %s\n"
                             % field['name'])
        else:
            sys.stdout.write("%s.\n" % message)
