# su_export_views.rb - export every SketchUp scene as a 2D DWG for the permit set.
# Run in SketchUp: Window > Ruby Console:  load 'D:/ANS/Claude/CAD train AI/lao-permit-cad/tools/su_export_views.rb'
# Scene names decide the sheet: prefix with the sheet no, e.g. "A202 ແຜນຜັງ ຊັ້ນ 1", "A301 ຮູບດ້ານໜ້າ", "A311 ຮູບຕັດ A-A".
# Each scene should be: Camera > Parallel Projection + standard view (Top/Front/...), section plane active for sections.
# NOTE: untested against every SketchUp version; if export fails use File > Export > 2D Graphic > AutoCAD DWG
# with "Full scale (1:1)", units mm, and save as <sheet>.dwg in the same folder.

module LaoPermitExport
  def self.run(out_dir = nil)
    model = Sketchup.active_model
    out_dir ||= File.join(File.dirname(model.path), 'cad_views')
    Dir.mkdir(out_dir) unless File.directory?(out_dir)
    pages = model.pages
    if pages.count == 0
      UI.messagebox('No scenes. Create scenes named like "A202 ແຜນຜັງ ຊັ້ນ 1".')
      return
    end
    done = []
    pages.each do |pg|
      pages.selected_page = pg
      model.active_view.camera.perspective = false
      sheet = pg.name.split(' ').first
      path = File.join(out_dir, "#{sheet}.dwg")
      # 2D vector export uses the current view; options follow the 2D DWG exporter
      ok = model.export(path, { :show_summary => false, :faces_flag => false, :edges => true,
                                :scale_to_drawing => true, :units => 'mm' })
      done << "#{sheet}: #{ok ? 'ok' : 'FAILED'}"
    end
    File.write(File.join(out_dir, 'export_log.txt'), done.join("\n"))
    UI.messagebox("Exported #{done.size} views to #{out_dir}")
  end
end

LaoPermitExport.run
