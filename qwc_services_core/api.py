from flask_restx import Api as BaseApi
from collections import OrderedDict
from werkzeug.datastructures import MultiDict
from flask_restx.reqparse import Argument

import os


class Api(BaseApi):
    """Custom Flask-RESTPlus Api subclass for overriding default root route

    NOTE: endpoint of route '/' must be named 'root'::

    >>> @api.route('/', endpoint='root')

    see also https://github.com/noirbizarre/flask-restplus/issues/247
    """
    def _register_doc(self, app_or_blueprint):
        if self._add_specs and self._doc:
            # Register documentation before root if enabled
            app_or_blueprint.add_url_rule(self._doc, "doc", self.render_doc)
        if not self.app.config.get("RESTX_NO_DEFAULT_ROOT_RULE"):
            app_or_blueprint.add_url_rule(self.prefix or "/", "root", self.render_root)

    def register_resource(self, namespace, resource, *urls, **kwargs):
        if "/" in urls and not self.app.config.get("RESTX_NO_DEFAULT_ROOT_RULE"):
            self.app.logger.warning("Attempting to register a resource to '/', which overlaps the default RESTX root rule.")
            self.app.logger.warning("Set the app config variable RESTX_NO_DEFAULT_ROOT_RULE to True before initializing the Api to prevent registering the default RESTX root rule.")
        elif "/" in urls and kwargs.get("endpoint") != "root":
            self.app.logger.warning("The '/' resource rule must be declared with endpoint='root'")
        super().register_resource(namespace, resource, *urls, **kwargs)

    def create_model(self, name, fields):
        """Helper for creating api models with ordered fields

        :param str name: Model name
        :param list fields: List of tuples containing ['field name', <type>]
        """
        return create_model(self, name, fields)

    def route(self, *urls, **kwargs):
        """Override for flask_restx @api.route but registers the resource only if
           ENABLED_ENDPOINTS is empty or if ENABLED_ENDPOINTS contains the route name
           and DISABLED_ENDPOINTS does not contain the route name.
        """

        whitelist = list(filter(bool, os.getenv("ENABLED_ENDPOINTS", "").split(",")))
        blacklist = list(filter(bool, os.getenv("DISABLED_ENDPOINTS", "").split(",")))

        def decorator(cls):
            route_name = kwargs.get("endpoint") or self.default_endpoint(cls, self.default_namespace)
            if (not whitelist or route_name in whitelist) and route_name not in blacklist:
                self.app.logger.debug("Registering route %s with URL(s) %s" % (route_name, ", ".join(urls)))
                return self.default_namespace.route(*urls, **kwargs)(cls)

            # Don't register -> won't appear in Swagger either.
            return cls

        return decorator

def create_model(api, name, fields):
    """Helper for creating api models with ordered fields

    :param flask_restx.Api api: Flask-RESTX Api object
    :param str name: Model name
    :param list fields: List of tuples containing ['field name', <type>]
    """
    d = OrderedDict()
    for field in fields:
        d[field[0]] = field[1]
    return api.model(name, d)


class CaseInsensitiveMultiDict(MultiDict):
    """ A MultiDict subclass to use with RequestParser which is
        case-insensitives for query parameter key names
    """
    def __init__(self, mapping=None):
        super().__init__(mapping)
        # map lowercase keys to the real keys
        self.lower_key_map = {key.lower(): key for key in self}

    def __contains__(self, key):
        return key.lower() in self.lower_key_map

    def getlist(self, key):
        return super().getlist(self.lower_key_map.get(key.lower()))

    def pop(self, key):
        return super().pop(self.lower_key_map.get(key.lower()))


class CaseInsensitiveArgument(Argument):
    def source(self, request):
        return CaseInsensitiveMultiDict(super().source(request))
