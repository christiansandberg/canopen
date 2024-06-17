# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
from importlib import metadata
sys.path.insert(0, os.path.abspath('..'))


# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'canopen'
project_copyright = '2016, Christian Sandberg'
author = 'Christian Sandberg'
# The full version, including alpha/beta/rc tags.
release = metadata.version('canopen')
# The short X.Y version.
version = '.'.join(release.split('.')[:2])

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode',
    'sphinx_autodoc_typehints',
]

templates_path = ['_templates']
root_doc = 'index'
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

language = 'en'

# Include documentation from both the class level and __init__
autoclass_content = 'both'

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_static_path = ['_static']

# Output file base name for HTML help builder.
htmlhelp_basename = 'canopendoc'

# -- Options for LaTeX output ---------------------------------------------

latex_documents = [
    (root_doc, 'canopen.tex', 'canopen Documentation',
     'Christian Sandberg', 'manual'),
]

# -- Options for manual page output ---------------------------------------

man_pages = [
    (root_doc, 'canopen', 'canopen Documentation',
     [author], 1)
]

# -- Options for Texinfo output -------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (root_doc, 'canopen', 'canopen Documentation',
     author, 'canopen', 'One line description of project.',
     'Miscellaneous'),
]

# -- Options for intersphinx extension ---------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/intersphinx.html#configuration

intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
    'can': ('https://python-can.readthedocs.io/en/stable/', None),
}
