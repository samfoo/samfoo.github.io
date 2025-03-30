# class BuildCleaner < Middleman::Extension
#   def initialize(app, options_hash={}, &block)
#     super
#     FileUtils.rm_rf app.config[:build_dir]
#   end
# end
#
# ::Middleman::Extensions.register(:build_cleaner, BuildCleaner)
#

set :css_dir, 'stylesheets'
set :js_dir, 'javascripts'
set :images_dir, 'images'

Encoding.default_internal = Encoding::UTF_8
Encoding.default_external = Encoding::UTF_8
set :encoding, "utf-8"

set :markdown_engine, :redcarpet
# set :markdown, input: "GFM"

page "/resume*", :layout => "layout"
page "/pages/*", :layout => "layout"

helpers do
  def markdown(text)
    Tilt['markdown'].new(context: @app) { text }.render
  end
end

configure :build do
  # activate :minify_css
  # activate :minify_javascript
  activate :asset_hash
  activate :relative_assets
end

activate :deploy do |deploy|
  deploy.deploy_method = :git
  # remote is optional (default is "origin")
  # run `git remote -v` to see a list of possible remotes
  # deploy.remote = "some-other-remote-name"

  # branch is optional (default is "gh-pages")
  # run `git branch -a` to see a list of possible branches
  deploy.branch = "master"

  # strategy is optional (default is :force_push)
  # deploy.strategy = :submodule
end
