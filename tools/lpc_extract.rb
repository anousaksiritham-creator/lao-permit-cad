# lpc_extract.rb - LaoPermitExtract v2: drawing geometry from the open SketchUp model.
# Defines the module only. Run from the Ruby Console with su_extract.rb, or from the
# HTML MCP v2 bridge command `lpc_extract` (this file is bundled in the extension).
#
# Output <out_root>/<model>/model.json:
#   objects  [{code,name,tag,min,max}]
#   plans    [{z, segs:[[x1,y1,x2,y2,code,kind]]}]           kind: cut | beyond
#   views    {top|front|back|left|right: {segs:[[u1,v1,u2,v2,code,'vis']]}}
#   sections [{name, axis, at, segs:[[u1,v1,u2,v2,code,kind]]}]
# Hidden lines are removed with model.raytest (glass and skipped components see-through).
# The model is never changed: all work happens inside one aborted operation.
require 'json'
require 'fileutils'

module LaoPermitExtract
  MM = 25.4
  DEFAULTS = { 'out_root' => 'D:/ANS/Claude/CAD train AI/lao-permit-cad/out', 'cuts' => [1500],
               'skip' => ['17 '], 'hidden' => true, 'sections' => 'auto', 'max_segs' => 120_000 }.freeze

  class << self
    def mm(v) (v * MM).round(1) end
    def inch(v) v / MM end

    # ---------- status ----------
    def status(state, step, extra = {})
      return unless @dir
      File.write(File.join(@dir, 'status.json'),
                 JSON.generate({ job: @job, state: state, step: step, t: (Time.now - @t0).round(1) }.merge(extra)))
    rescue StandardError
      nil
    end

    # ---------- entity helpers ----------
    def name_of(e)
      e.name.to_s.empty? && e.respond_to?(:definition) ? e.definition.name : e.name.to_s
    end

    def code_of(e) name_of(e).split(' ').first.to_s end

    def instance?(e) e.is_a?(Sketchup::Group) || e.is_a?(Sketchup::ComponentInstance) end

    def ents_of(e) e.is_a?(Sketchup::Group) ? e.entities : e.definition.entities end

    def shown?(e)
      return false if e.respond_to?(:hidden?) && e.hidden?
      return false if e.respond_to?(:layer) && e.layer && !e.layer.visible?
      true
    end

    def tops
      @model.entities.select { |e| instance?(e) && shown?(e) }
    end

    # faces (world transform) under one top-level instance
    def each_face(ents, tr, &blk)
      ents.each do |e|
        next unless shown?(e)
        if e.is_a?(Sketchup::Face) then blk.call(e, tr)
        elsif instance?(e) then each_face(ents_of(e), tr * e.transformation, &blk)
        end
      end
    end

    def transparent?(path)
      path.to_a.any? do |e|
        (e.respond_to?(:material) && e.material && e.material.alpha < 0.95) ||
          (e.is_a?(Sketchup::Face) && e.back_material && e.back_material.alpha < 0.95)
      end
    end

    # true when point p (inches) is visible toward dir. blocked.(hit) false = hit in a
    # removed region (above a plan cut / in front of a section) -> ignore and continue.
    def clear?(p, dir, &blocked)
      return true unless @hidden
      start = p.offset(dir, inch(2))
      4.times do
        hit = @model.raytest([start, dir], true)
        return true unless hit
        pt, path = hit
        return false if blocked.call(pt) && !transparent?(path)
        start = pt.offset(dir, inch(1))
      end
      true
    end

    # split p1-p2 into samples, keep visible runs
    def visible_runs(p1, p2, dir, &blocked)
      len = p1.distance(p2)
      n = [[(mm(len) / 300).ceil, 2].max, 12].min
      vis = (0..n).map { |i| clear?(Geom::Point3d.linear_combination(1 - i.to_f / n, p1, i.to_f / n, p2), dir, &blocked) }
      runs = []
      s = nil
      vis.each_with_index do |v, i|
        if v && s.nil? then s = i
        elsif !v && s
          runs << [s, i - 1] if i - 1 > s
          s = nil
        end
      end
      runs << [s, n] if s && n > s
      runs.map do |a, b|
        [Geom::Point3d.linear_combination(1 - a.to_f / n, p1, a.to_f / n, p2),
         Geom::Point3d.linear_combination(1 - b.to_f / n, p1, b.to_f / n, p2)]
      end
    end

    # ---------- projection with hidden-line ----------
    # dir: unit vector from model toward viewer; uv: Point3d -> [u,v]; keep: Point3d -> bool (geometry region)
    def project(dir, uv, keep = nil, &blocked)
      blocked ||= ->(_pt) { true }
      seen = {}
      segs = []
      tops.each do |top|
        code = code_of(top)
        each_face(ents_of(top), top.transformation) do |f, tr|
          n = f.normal.transform(tr)
          next if n.length.zero?
          n.normalize!
          next unless n.dot(dir) > 0.02
          f.edges.each do |ed|
            next if ed.soft? || ed.smooth? || ed.hidden?
            p1 = ed.start.position.transform(tr)
            p2 = ed.end.position.transform(tr)
            next if keep && !(keep.call(p1) && keep.call(p2))
            key = [p1.to_a.map { |c| c.round(2) }, p2.to_a.map { |c| c.round(2) }].sort.flatten.join(',')
            next if seen[key]
            seen[key] = true
            visible_runs(p1, p2, dir, &blocked).each do |a, b|
              ua = uv.call(a).map { |c| mm(c) }
              ub = uv.call(b).map { |c| mm(c) }
              next if ua == ub
              segs << ua + ub + [code, 'vis']
            end
            return segs if segs.size >= @max
          end
        end
      end
      segs
    end

    # ---------- planar cut ----------
    # plane given by 4 corner points (inches); returns [[p1,p2,code]] world points
    def cut(corners)
      out = []
      pts = corners.map { |c| Geom::Point3d.new(*c) }
      border = (pts.each_cons(2).to_a << [pts[-1], pts[0]]).map { |c1, c2| [c1, c2 - c1] }
      tops.each do |top|
        g = @model.entities.add_group
        g.entities.add_face(pts)
        g.entities.intersect_with(true, g.transformation, g.entities, g.transformation, false, [top])
        g.entities.grep(Sketchup::Edge).each do |ed|
          a = ed.start.position
          b = ed.end.position
          on_border = border.any? { |line| a.on_line?(line) && b.on_line?(line) }
          out << [a, b, code_of(top)] unless on_border
        end
        g.erase!
      end
      out
    end

    def children(top)
      tr = top.transformation
      ents_of(top).select { |e| instance?(e) && shown?(e) }.first(400).map do |e|
        bb = Geom::BoundingBox.new
        e.bounds.then { |b| (0..7).each { |i| bb.add(b.corner(i).transform(tr)) } }
        { name: name_of(e), min: bb.min.to_a.map { |c| mm(c) }, max: bb.max.to_a.map { |c| mm(c) } }
      end
    end

    # all edges of faces facing dir, no hidden-line (for structure / MEP plans filtered by code)
    def xray(dir, uv)
      seen = {}
      segs = []
      tops.each do |top|
        code = code_of(top)
        each_face(ents_of(top), top.transformation) do |f, tr|
          n = f.normal.transform(tr)
          next if n.length.zero?
          n.normalize!
          next unless n.dot(dir).abs > 0.02
          f.edges.each do |ed|
            next if ed.soft? || ed.smooth? || ed.hidden?
            ua = uv.call(ed.start.position.transform(tr)).map { |c| mm(c) }
            ub = uv.call(ed.end.position.transform(tr)).map { |c| mm(c) }
            next if ua == ub
            key = (ua + ub).join(',') + code
            next if seen[key]
            seen[key] = true
            segs << ua + ub + [code, 'xray']
            return segs if segs.size >= @max
          end
        end
      end
      segs
    end

    # Auto section planes: middle of the column bay nearest the building centre (columns = children
    # of the '04' component, <= 600 mm square, > 1.5 m tall), so the cut never runs along a grid.
    # Building = walls '08' if present. Falls back to the centre of the bounds.
    def auto_section_positions(bb)
      walls = tops.find { |e| code_of(e) == '08' }
      fb = walls ? walls.bounds : bb
      cx = (fb.min.x + fb.max.x) / 2
      cy = (fb.min.y + fb.max.y) / 2
      cols = tops.find { |e| code_of(e) == '04' }
      return [cx, cy] unless cols
      xs = []
      ys = []
      ents_of(cols).each do |e|
        next unless instance?(e)
        b = Geom::BoundingBox.new
        (0..7).each { |i| b.add(e.bounds.corner(i).transform(cols.transformation)) }
        next unless b.width <= inch(600) && b.height <= inch(600) && b.depth > inch(1500)
        xs << b.center.x
        ys << b.center.y
      end
      mid = lambda do |vals, c|
        g = vals.sort.chunk_while { |p, q| q - p < inch(150) }.map { |grp| grp.sum / grp.size }
        return c if g.size < 2
        bays = g.each_cons(2).map { |p, q| (p + q) / 2 }
        bays.min_by { |m| (m - c).abs }
      end
      [mid.call(xs, cx), mid.call(ys, cy)]
    end

    def bounds_of(list)
      bb = Geom::BoundingBox.new
      list.each { |e| bb.add(e.bounds) }
      bb
    end

    # ---------- main ----------
    def run(args = {})
      a = DEFAULTS.merge(args || {})
      @model = Sketchup.active_model
      @t0 = Time.now
      @job = a['job'] || Time.now.strftime('%H%M%S')
      @hidden = a['hidden'] != false
      @max = Integer(a['max_segs'])
      base = File.basename(@model.path.to_s, '.skp')
      base = 'untitled' if base.empty?
      @dir = File.join(a['out_root'], base)
      FileUtils.mkdir_p(@dir)
      status('running', 'start')
      data = nil
      @model.start_operation('LPC extract (temporary)', true)
      begin
        skip = Array(a['skip'])
        @model.entities.each { |e| e.hidden = true if instance?(e) && skip.any? { |p| name_of(e).start_with?(p) } }
        bb = bounds_of(tops)
        pad = inch(500)
        x0, y0, x1, y1 = bb.min.x - pad, bb.min.y - pad, bb.max.x + pad, bb.max.y + pad
        z0, z1 = bb.min.z - pad, bb.max.z + pad
        data = {
          version: 2, units: 'mm', up_axis: 'Z', model_guid: @model.guid, job: @job, model: @model.path, title: @model.title, sketchup: Sketchup.version,
          bounds_mm: { min: bb.min.to_a.map { |c| mm(c) }, max: bb.max.to_a.map { |c| mm(c) } },
          objects: tops.map { |e| b = e.bounds; { persistent_id: e.persistent_id, code: code_of(e), name: name_of(e), tag: e.layer ? e.layer.name : '',
                                                  min: b.min.to_a.map { |c| mm(c) }, max: b.max.to_a.map { |c| mm(c) },
                                                  children: children(e) } },
          materials: @model.materials.map { |m| { name: m.name, alpha: m.alpha } },
          scenes: @model.pages.map(&:name),
          plans: [], views: {}, sections: []
        }
        # plans: cut + beyond (looking down, geometry below the cut)
        Array(a['cuts']).each do |zmm|
          status('running', "plan #{zmm}")
          z = inch(zmm)
          c = cut([[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z]])
          segs = c.map { |p, q, code| [mm(p.x), mm(p.y), mm(q.x), mm(q.y), code, 'cut'] }
          below = ->(p) { p.z < z - inch(1) }
          segs += project(Geom::Vector3d.new(0, 0, 1), ->(p) { [p.x, p.y] }, below) { |pt| pt.z < z - inch(1) }
                  .map { |s| s[0..4] + ['beyond'] }
          data[:plans] << { z: zmm, segs: segs }
        end
        # elevations + roof view
        { 'top' => [[0, 0, 1], ->(p) { [p.x, p.y] }], 'front' => [[0, -1, 0], ->(p) { [p.x, p.z] }],
          'back' => [[0, 1, 0], ->(p) { [-p.x, p.z] }], 'left' => [[-1, 0, 0], ->(p) { [-p.y, p.z] }],
          'right' => [[1, 0, 0], ->(p) { [p.y, p.z] }] }.each do |k, (d, uv)|
          status('running', "view #{k}")
          data[:views][k] = { segs: project(Geom::Vector3d.new(*d), uv) }
        end
        status('running', 'xray top')
        data[:views]['top_xray'] = { segs: xray(Geom::Vector3d.new(0, 0, 1), ->(p) { [p.x, p.y] }) }
        # sections: model section planes, else A-A across Y centre and B-B across X centre
        planes = @model.entities.grep(Sketchup::SectionPlane).map do |sp|
          pa = sp.get_plane
          nrm = Geom::Vector3d.new(pa[0], pa[1], pa[2])
          axis = nrm.x.abs > nrm.y.abs ? 'x' : 'y'
          at = -pa[3] / (axis == 'x' ? pa[0] : pa[1])
          { name: sp.name.to_s.empty? ? sp.symbol.to_s : sp.name, axis: axis, at: at, look: axis == 'x' ? (pa[0] > 0 ? 1 : -1) : (pa[1] > 0 ? 1 : -1) }
        end.select { |s| s[:at].finite? }
        if planes.empty? && a['sections'] == 'auto'
          ax, ay = auto_section_positions(bb)
          planes = [{ name: 'A-A', axis: 'y', at: ay, look: 1 },
                    { name: 'B-B', axis: 'x', at: ax, look: 1 }]
        end
        planes.each do |s|
          status('running', "section #{s[:name]}")
          at = s[:at]
          if s[:axis] == 'y'
            corners = [[x0, at, z0], [x1, at, z0], [x1, at, z1], [x0, at, z1]]
            # keep geometry on the +look side; viewer stands on the other side
            sign = s[:look]
            dir = Geom::Vector3d.new(0, -sign, 0)
            uv = sign > 0 ? ->(p) { [p.x, p.z] } : ->(p) { [-p.x, p.z] }
            side = ->(p) { (p.y - at) * sign }
          else
            corners = [[at, y0, z0], [at, y1, z0], [at, y1, z1], [at, y0, z1]]
            sign = s[:look]
            dir = Geom::Vector3d.new(-sign, 0, 0)
            uv = sign > 0 ? ->(p) { [-p.y, p.z] } : ->(p) { [p.y, p.z] }
            side = ->(p) { (p.x - at) * sign }
          end
          c = cut(corners)
          segs = c.map { |p, q, code| uv.call(p).map { |v| mm(v) } + uv.call(q).map { |v| mm(v) } + [code, 'cut'] }
          keep = ->(p) { side.call(p) > inch(1) }
          segs += project(dir, uv, keep) { |pt| side.call(pt) > inch(1) }.map { |q| q[0..4] + ['beyond'] }
          data[:sections] << { name: s[:name], axis: s[:axis], at: mm(at), look: s[:look], segs: segs }
        end
      ensure
        @model.abort_operation
      end
      File.write(File.join(@dir, 'model.json'), JSON.generate(data))
      summary = { plans: data[:plans].map { |p| p[:segs].size }, views: data[:views].transform_values { |v| v[:segs].size },
                  sections: data[:sections].map { |s| [s[:name], s[:segs].size] } }
      status('done', 'written', summary: summary, path: File.join(@dir, 'model.json'))
      summary
    rescue StandardError => e
      status('error', 'failed', error: "#{e.class}: #{e.message}", at: e.backtrace.to_a.first(4))
      raise
    end
  end
end
