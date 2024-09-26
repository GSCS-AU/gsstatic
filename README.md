# GSStatic
GS Static is a static website builder built with Python and Jinja2 with inspiration from django-jinja.

Borrows heavily from staticjinja but makes Jinja more of the focus. Uses ideas (and some code) from django-jinja about how the enviroment can be configured.

Supports the idea of an input directory which holds templates to be rendered but adds extra template directories which are added to the template resolution path. In this way the output folder mirrors the input folder with partials stored outside of this structure.

Supports adding a `tags` directory which holds template tags, global functions, filters and tests that can be automatically added to the enviroment. This is the core path for adding extra code / features to templates.

Context has been simplified to a callable that takes a template name. The same callable is used for all templates. What form this takes and what happens after is up to the user.

