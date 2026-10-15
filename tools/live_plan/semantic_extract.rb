# Read-only SketchUp 2025 extraction. Loading this file does not export or edit.
# Ruby Console:
# load 'C:/path/to/repo/tools/live_plan/semantic_extract.rb'
# LaoPermitCad::SemanticExtract.export(path: 'C:/scratch/source.json', cut_mm: 1500,
#   expected_title: 'My model')
require 'json'
require 'time'
require 'securerandom'

module LaoPermitCad
  module SemanticExtract
    MM = 25.4
    def self.export(path:, cut_mm:, expected_title: nil)
      model = Sketchup.active_model
      raise 'Exit group/component editing first' if model.active_path
      raise 'Wrong model' if expected_title && model.title != expected_title
      raise 'Explicit finite cut_mm required' unless cut_mm.is_a?(Numeric) && cut_mm.finite?
      raise 'Will not overwrite snapshot' if File.exist?(path)
      @cut = cut_mm.to_f
      @objects = []; @segments = []; @texts = []; @hidden = []; @coplanar = 0
      walk(model.entities, Geom::Transformation.new, [], true)
      session = defined?(SketchupHTMLMCPV2) ? SketchupHTMLMCPV2.instance_variable_get(:@session) : nil
      data = { version: 1, units: 'mm', title: model.title, path: model.path,
               sketchup_version: Sketchup.version, model_session: session,
               captured_at: Time.now.utc.iso8601, cut_mm: @cut,
               display_units: model.options['UnitsOptions'].to_h,
               objects: @objects, segments: @segments, texts: @texts, hidden: @hidden,
               warnings: { coplanar_triangles_skipped: @coplanar,
                 below_projection: 'Actual lower edges; no occlusion removal or architectural inference' } }
      temp = "#{path}.#{SecureRandom.hex(6)}.tmp"
      begin
        File.write(temp, JSON.generate(data))
        raise 'Destination appeared during export' if File.exist?(path)
        File.rename(temp, path)
      ensure
        File.delete(temp) if File.exist?(temp)
      end
      puts "Read #{model.title}: #{@objects.length} instances, #{@segments.length} segments, #{@hidden.length} hidden"
      path
    end

    def self.xyz(p, tr)
      values = p.transform(tr).to_a.map { |v| v.to_f * MM }
      raise 'Non-finite source geometry' unless values.all?(&:finite?)
      values
    end

    def self.emit(a, b, kind, path, extra = {})
      raise 'Extraction exceeds 500000 segments' if @segments.length >= 500_000
      @segments << { a: a[0, 2], b: b[0, 2], kind: kind, path: path,
                     source_id: path.map { |p| p[:id] }.join('/') }.merge(extra)
    end

    def self.walk(entities, tr, path, visible)
      entities.each do |e|
        shown = visible && !(e.respond_to?(:hidden?) && e.hidden?) &&
                !(e.respond_to?(:layer) && !e.layer.visible?)
        if e.is_a?(Sketchup::Group) || e.is_a?(Sketchup::ComponentInstance)
          name = e.name.to_s
          name = e.definition.name if name.empty? && e.respond_to?(:definition)
          branch = path + [{ id: e.persistent_id, name: name }]
          record = { source_id: branch.map { |p| p[:id] }.join('/'), path: branch,
                     visible: shown, tag: e.layer.name, locked: e.locked? }
          @objects << record; @hidden << record unless shown
          children = e.is_a?(Sketchup::Group) ? e.entities : e.definition.entities
          # Inspect hidden descendants as metadata, but never export their geometry.
          walk(children, tr * e.transformation, branch, shown)
        elsif shown && e.is_a?(Sketchup::Face)
          mesh = e.mesh(0); vertices = mesh.points.map { |p| xyz(p, tr) }
          mesh.polygons.each do |polygon|
            pts = polygon.map { |i| vertices[i.abs - 1] }
            (1...pts.length - 1).each do |j|
              triangle = [pts[0], pts[j], pts[j + 1]]
              if triangle.all? { |p| (p[2] - @cut).abs < 1e-6 }
                @coplanar += 1; next
              end
              hits = []
              triangle.each_with_index do |a, i|
                b = triangle[(i + 1) % 3]; da = a[2] - @cut; db = b[2] - @cut
                hits << a if da.abs < 1e-6
                if da * db < -1e-12
                  t = -da / (db - da)
                  hits << [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), @cut]
                end
              end
              hits = hits.uniq { |p| p.map { |v| v.round(5) } }
              emit(hits[0], hits[1], 'cut', path) if hits.length == 2
            end
          end
          # Use transformed triangle edges: normal.transform(tr) is incorrect
          # under non-uniform instance scaling.
          first = mesh.polygons.first
          a, b, c = first.first(3).map { |i| vertices[i.abs - 1] }
          normal_z = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
          if normal_z.abs > 1e-8
            e.edges.each do |edge|
              next if edge.hidden? || edge.soft? || edge.smooth?
              a = xyz(edge.start.position, tr); b = xyz(edge.end.position, tr)
              next unless [a[2], b[2]].max < @cut - 1e-6 && [a[2], b[2]].min >= -1e-6
              emit(a, b, 'below', path, z: [a[2], b[2]])
            end
          end
        elsif shown && e.is_a?(Sketchup::Edge) && path.any? { |p| p[:name].downcase.include?('grid') }
          emit(xyz(e.start.position, tr), xyz(e.end.position, tr), 'grid', path)
        elsif shown && e.is_a?(Sketchup::Text)
          @texts << { text: e.text, point: xyz(e.point, tr), path: path }
        end
      end
    end
  end
end
