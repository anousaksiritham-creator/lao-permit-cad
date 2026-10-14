# su_extract.rb - pull 2D drawing geometry out of the open SketchUp model for AutoCAD.
# SketchUp > Window > Ruby Console:
#   load 'D:/ANS/Claude/CAD train AI/lao-permit-cad/tools/su_extract.rb'
# Optional before loading: $LPC_CUTS = [1500] (absolute Z mm of plan cuts), $LPC_SKIP = ['17 '] (name prefixes to ignore)
# Output: lao-permit-cad/out/<model>/model.json + view PNGs. Model is not changed (cuts are aborted).
require 'json'

module LaoPermitExtract
  MM = 25.4 # SketchUp internal unit = inch
  OUT_ROOT = 'D:/ANS/Claude/CAD train AI/lao-permit-cad/out'

  def self.mm(v) (v * MM).round(1) end

  def self.skip?(e)
    return false unless e.is_a?(Sketchup::Group) || e.is_a?(Sketchup::ComponentInstance)
    n = e.name.to_s.empty? && e.respond_to?(:definition) ? e.definition.name : e.name.to_s
    ($LPC_SKIP || ['17 ']).any? { |p| n.start_with?(p) }
  end

  def self.visible?(e)
    return false if skip?(e)
    return false if e.respond_to?(:hidden?) && e.hidden?
    return false if e.respond_to?(:layer) && e.layer && !e.layer.visible?
    true
  end

  # Walk all faces with world transforms.
  # top = code of the top-level object ("08" from "08 ຝາ + ...") so views can be filtered later.
  def self.code(e)
    n = e.name.to_s.empty? && e.respond_to?(:definition) ? e.definition.name : e.name.to_s
    n.split(' ').first.to_s
  end

  def self.each_face(ents, tr, top = '', &blk)
    ents.each do |e|
      next unless visible?(e)
      t = top.empty? && (e.is_a?(Sketchup::Group) || e.is_a?(Sketchup::ComponentInstance)) ? code(e) : top
      case e
      when Sketchup::Face then blk.call(e, tr, t)
      when Sketchup::Group then each_face(e.entities, tr * e.transformation, t, &blk)
      when Sketchup::ComponentInstance then each_face(e.definition.entities, tr * e.transformation, t, &blk)
      end
    end
  end

  # Elevation / top projection: outer loops of faces that face the viewer.
  # view: [viewer_dir(Vector3d pointing from model to viewer), u-axis proc, v-axis proc]
  VIEWS = {
    'top'   => [Geom::Vector3d.new(0, 0, 1),  ->(p) { [p.x, p.y] }],
    'front' => [Geom::Vector3d.new(0, -1, 0), ->(p) { [p.x, p.z] }],
    'back'  => [Geom::Vector3d.new(0, 1, 0),  ->(p) { [-p.x, p.z] }],
    'left'  => [Geom::Vector3d.new(-1, 0, 0), ->(p) { [-p.y, p.z] }],
    'right' => [Geom::Vector3d.new(1, 0, 0),  ->(p) { [p.y, p.z] }]
  }

  def self.project(model, dir, uv, limit)
    seen = {}
    segs = []
    each_face(model.entities, Geom::Transformation.new) do |f, tr, top|
      n = f.normal.transform(tr)
      next if n.length == 0
      n.normalize!
      next unless n.dot(dir) > 0.05
      f.outer_loop.edges.each do |ed|
        a = uv.call(ed.start.position.transform(tr)).map { |c| mm(c) }
        b = uv.call(ed.end.position.transform(tr)).map { |c| mm(c) }
        next if a == b
        key = [a, b].sort.flatten.join(',')
        next if seen[key]
        seen[key] = true
        segs << a + b + [top]
        return [segs, true] if segs.size >= limit
      end
    end
    [segs, false]
  end

  # Horizontal plan cut: intersect a big plane with the model inside an aborted operation.
  def self.cut(model, z_mm)
    bb = model.bounds
    z = z_mm / MM
    pad = 100
    pts = [[bb.min.x - pad, bb.min.y - pad, z], [bb.max.x + pad, bb.min.y - pad, z],
           [bb.max.x + pad, bb.max.y + pad, z], [bb.min.x - pad, bb.max.y + pad, z]]
    segs = []
    model.start_operation('LPC cut', true)
    begin
      g = model.entities.add_group
      g.entities.add_face(pts)
      others = model.entities.to_a.select { |e| visible?(e) } - [g]
      g.entities.intersect_with(true, g.transformation, g.entities, g.transformation, false, others)
      g.entities.grep(Sketchup::Edge).each do |ed|
        p1 = ed.start.position; p2 = ed.end.position
        border = [p1, p2].all? { |p| (p.x - (bb.min.x - pad)).abs < 0.01 || (p.x - (bb.max.x + pad)).abs < 0.01 ||
                                      (p.y - (bb.min.y - pad)).abs < 0.01 || (p.y - (bb.max.y + pad)).abs < 0.01 }
        next if border
        segs << [mm(p1.x), mm(p1.y), mm(p2.x), mm(p2.y)]
      end
    ensure
      model.abort_operation
    end
    segs
  end

  def self.objects(model)
    list = []
    model.entities.each do |e|
      next unless (e.is_a?(Sketchup::Group) || e.is_a?(Sketchup::ComponentInstance)) && visible?(e)
      b = e.bounds
      name = e.name.to_s.empty? ? (e.respond_to?(:definition) ? e.definition.name : '') : e.name
      list << { name: name, tag: (e.layer ? e.layer.name : ''), type: e.typename,
                min: [mm(b.min.x), mm(b.min.y), mm(b.min.z)], max: [mm(b.max.x), mm(b.max.y), mm(b.max.z)] }
    end
    list
  end

  def self.snap(model, dir, name, eye_dir)
    view = model.active_view
    cam = view.camera
    saved = Sketchup::Camera.new(cam.eye, cam.target, cam.up, cam.perspective?)
    c = model.bounds.center
    eye = c.offset(eye_dir, model.bounds.diagonal * 2)
    up = eye_dir.z.abs > 0.9 ? Geom::Vector3d.new(0, 1, 0) : Geom::Vector3d.new(0, 0, 1)
    view.camera = Sketchup::Camera.new(eye, c, up, false)
    view.zoom_extents
    view.write_image(filename: File.join(dir, "#{name}.png"), width: 1600, height: 1000, antialias: true)
    view.camera = saved
  end

  def self.run
    model = Sketchup.active_model
    base = File.basename(model.path.to_s, '.skp')
    base = 'untitled' if base.empty?
    dir = File.join(OUT_ROOT, base)
    require 'fileutils'
    FileUtils.mkdir_p(dir)
    bb = model.bounds
    cuts = $LPC_CUTS || [1500]
    data = {
      model: model.path, title: model.title, sketchup: Sketchup.version,
      bounds_mm: { min: [mm(bb.min.x), mm(bb.min.y), mm(bb.min.z)], max: [mm(bb.max.x), mm(bb.max.y), mm(bb.max.z)] },
      tags: model.layers.map { |l| { name: l.name, visible: l.visible? } },
      scenes: model.pages.map(&:name),
      objects: objects(model),
      plans: cuts.map { |z| { z: z, segs: cut(model, z) } },
      views: {}
    }
    VIEWS.each do |k, (dir_v, uv)|
      segs, trunc = project(model, dir_v, uv, 60000)
      data[:views][k] = { segs: segs, truncated: trunc }
      snap(model, dir, k, dir_v)
    end
    File.write(File.join(dir, 'model.json'), JSON.generate(data))
    msg = "LPC export OK -> #{dir}\nobjects #{data[:objects].size}, plan segs #{data[:plans].map { |p| p[:segs].size }.inspect}, " \
          "views #{data[:views].map { |k, v| "#{k}:#{v[:segs].size}" }.join(' ')}"
    puts msg
    msg
  end
end

LaoPermitExtract.run
