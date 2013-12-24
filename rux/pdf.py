# coding=utf8

"""
    rux.pdf
    ~~~~~~~

    Generate PDF using wkhtmltopdf.
"""

import sys
import time
import subprocess
import os
from os import listdir as ls
from os.path import exists

from . import src_ext, charset
from .config import config
from .exceptions import *
from .parser import parser
from .renderer import renderer
from .logger import logger
from .models import blog, author, Post
from .utils import update_nested_dict, join


def render(template, **data):
    """shortcut to render data with `template`. Just add exception
    catch to `renderer.render`"""
    try:
        return renderer.render(template, **data)
    except JinjaTemplateNotFound as e:
        logger.error(e.__doc__ + ', Template: %r' % template)
        sys.exit(e.exit_code)


class PDFGenerator(object):

    def __init__(self):
        self.commands = ['wkhtmltopdf',
                         '-',
                         # '--quiet',  # Be less verbose
                         '--page-size',  # Set paper size to: A4
                         'A4',
                         '--outline',
                         '--outline-depth',  # Set the depth of the outline
                         '2',]
        self.config = config.default
        self.blog = blog
        self.author = author
        self.posts = []
        self.html = None

    def initialize(self):

        # read config
        try:
            conf = config.parse()
        except ConfigSyntaxError as e:
            logger.error(e.__doc__)
            sys.exit(e.exit_code)

        update_nested_dict(self.config, conf)

        self.blog.__dict__.update(self.config['blog'])
        self.author.__dict__.update(self.config['author'])

        # initialize jinja2
        templates = join(self.blog.theme, 'templates')  # templates directory path
        # set a renderer
        jinja2_global_data = {
            'blog': self.blog,
            'author': self.author,
            'config': self.config
        }
        renderer.initialize(templates, jinja2_global_data)

        logger.success('Initialized')

    def get_posts(self):
        if not exists(Post.src_dir):
            logger.error(SourceDirectoryNotFound.__doc__)
            sys.exit(SourceDirectoryNotFound.exit_code)

        source_files = [join(Post.src_dir, fn)
                        for fn in ls(Post.src_dir) if fn.endswith(src_ext)]

        for filepath in source_files:
            try:
                data = parser.parse_filename(filepath)
            except ParseException as e:  # skip single post parse exception
                logger.warn(e.__doc__ + ', filepath: %r' % filepath)
            else:
                self.posts.append(Post(**data))

        # sort posts by its created time, from new to old
        self.posts.sort(key=lambda post: post.datetime.timetuple(), reverse=True)

    def parse_posts(self):

        for post in self.posts:
            with open(post.filepath, 'r') as file:
                content = file.read()

            try:
                data = parser.parse(content)
            except ParseException, e:
                logger.warn(e.__doc__ + ', filepath %r' % post.filepath)
                pass
            else:
                post.__dict__.update(data)
        logger.success('Posts parsed')

    def render(self):
        self.html = render('pdf.html', posts=self.posts, BLOG_ABS_PATH=os.getcwd())
        logger.success('Posts rendered')

    def generate(self):
        start_time = time.time()
        self.initialize()
        self.get_posts()
        self.parse_posts()
        self.render()

        out = self.blog.name.encode(charset) + '.pdf'

        logger.info('Generate pdf with wkhtmltopdf:')
        self.commands.append(out)   # append output path
        proc = subprocess.Popen(self.commands, stdin=subprocess.PIPE,
                                stdout=sys.stdout, stderr=sys.stderr)
        stdout, stderr = proc.communicate(input=self.html.encode(charset))
        logger.success('Generated to %s in %.3f seconds' % (out, time.time() - start_time))


pdf_generator = PDFGenerator()