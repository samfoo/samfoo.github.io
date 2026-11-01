source 'https://rubygems.org'

# Must load before activesupport: concurrent-ruby >= 1.3.5 dropped its implicit
# `require "logger"`, and activesupport 6.1 references `Logger` at load time. On
# Ruby < 3.x that raises an uninitialized-constant error unless logger is required
# first — listing it here makes Bundler load it ahead of middleman/activesupport.
gem "logger"

gem "middleman"
gem "middleman-deploy", "~> 2.0.0.pre.alpha"
gem "redcarpet"
