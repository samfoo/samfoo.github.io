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

# The training log / plan markdown lives outside source/ (repo root) so it isn't
# published by default; the /training page renders it in at build time.
TRAINING_DIR = File.expand_path("training", __dir__)

page "/resume*", :layout => "layout"
page "/pages/*", :layout => "layout"

helpers do
  def markdown(text)
    Tilt['markdown'].new(context: @app) { text }.render
  end

  # Sorted absolute paths of the weekly log files (training/logs/YYYY-Www.md).
  def training_week_logs
    Dir.glob(File.join(TRAINING_DIR, "logs", "*.md")).sort
  end

  # Render a training markdown doc (path relative to TRAINING_DIR) to HTML.
  # Tables/fenced code are enabled explicitly (redcarpet defaults them off), and
  # the docs' inter-file .md links are rewritten to in-page anchors.
  def render_training(relative_path)
    text = File.read(File.join(TRAINING_DIR, relative_path))
    renderer = Redcarpet::Markdown.new(
      Redcarpet::Render::HTML.new,
      tables: true, fenced_code_blocks: true, autolink: true,
      strikethrough: true, no_intra_emphasis: true, space_after_headers: true
    )
    html = renderer.render(text)
    # strength.md is shown on the page — point its links at the in-page anchor.
    html = html.gsub(%r{href="(?:\.\./)?strength\.md"}, 'href="#strength"')
    # plan / principles / README aren't shown on the web page — unwrap those
    # links so they render as plain text instead of dead anchors.
    html.gsub(%r{<a href="(?:\.\./)?(?:plan|principles|README)\.md">(.*?)</a>}m, '\1')
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
