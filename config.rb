###
# Compass
###

# Change Compass configuration
# compass_config do |config|
#   config.output_style = :compact
# end

###
# Page options, layouts, aliases and proxies
###

# Per-page layout changes:
#
# With no layout
# page "/path/to/file.html", :layout => false
#
# With alternative layout
# page "/path/to/file.html", :layout => :otherlayout
#
# A path which all have the same layout
# with_layout :admin do
#   page "/admin/*"
# end

# Proxy pages (https://middlemanapp.com/advanced/dynamic_pages/)
# proxy "/this-page-has-no-template.html", "/template-file.html", :locals => {
#  :which_fake_page => "Rendering a fake page with a local variable" }

###
# Helpers
###

# Automatic image dimensions on image_tag helper
# activate :automatic_image_sizes

# Reload the browser automatically whenever files change
# configure :development do
#   activate :livereload
# end

# Methods defined in the helpers block are available in templates
# helpers do
#   def some_helper
#     "Helping"
#   end
# end

set :css_dir, 'stylesheets'
set :js_dir, 'javascripts'
set :images_dir, 'images'

require "markdown_checkboxes"
require "action_view"
# renderer = CheckboxMarkdown.new(Redcarpet::Render::HTML.new())
class Redcarpet::Markdown
  include ActionView::Helpers::FormTagHelper
  alias_method :render_orig, :render

  def render(text, &block)
    text = render_checkboxes(text, &block)
    render_orig text
  end

  def render_checkboxes(text, &block)
    checkbox_regex  = /\*\s?\[(x|\s)\]/

    text.gsub(checkbox_regex).with_index do |current_match, current_index|
      checked = current_match =~ /x/ ? true : false

      body =
        text.gsub(checkbox_regex).with_index do |match, index|
          if index == current_index
            checked ? "* [ ]" : "* [x]"
          else
            match
          end
        end

      check_box_tag "check_#{current_index}", "", checked, data: data_options(body, &block)
    end
  end

  def data_options(body)
    if block_given?
      data_struct = DataStruct.new
      yield(data_struct, body)
      data_struct.serializable_hash
    else
      {}
    end
  end
end

renderer = Redcarpet::Render::HTML.new()

set :markdown_engine, :redcarpet
set :markdown, input: "GFM", tables: true, autolink: true, renderer: renderer

page "/resume*", :layout => "layout"
page "/pages/*", :layout => "layout"

helpers do
  def markdown(text)
    Tilt['markdown'].new { text }.render
  end
end

configure :build do
  activate :minify_css
  activate :minify_javascript
  activate :asset_hash
  activate :relative_assets
  activate :livereload
end

activate :deploy do |deploy|
  deploy.method = :git
  # remote is optional (default is "origin")
  # run `git remote -v` to see a list of possible remotes
  # deploy.remote = "some-other-remote-name"

  # branch is optional (default is "gh-pages")
  # run `git branch -a` to see a list of possible branches
  deploy.branch = "master"

  # strategy is optional (default is :force_push)
  # deploy.strategy = :submodule
end
