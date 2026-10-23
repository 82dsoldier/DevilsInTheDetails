{
  Place the hammerhead barracks in DevilsInTheDetails.esp from out\barracks\barracks_placements.csv
  (written by scripts/make_barracks.py).

  For each row it makes (or updates) a static, DevilsBarracksNN, with the row's model and bounds,
  and one reference to it in the right cell of DevilsBarracksWorld at the row's position and
  rotation. Run it again after the buildings change: it updates what is there instead of adding
  more.

  To use: copy this file into FO4Edit's "Edit Scripts" folder, start FO4Edit with
  DevilsInTheDetails.esp, right-click the plugin, Apply Script, pick DevilsPlaceBarracks. It reads
  the list from DefaultCsv below.
}
unit DevilsPlaceBarracks;

const
  PluginName = 'DevilsInTheDetails.esp';
  WorldName = 'DevilsBarracksWorld';
  DefaultCsv = 'C:sourceeposBraggMapoutbarracksbarracks_placements.csv';   // where make_barracks.py writes it

var
  Cells: TStringList;     // 'x,y' -> index into CellRecs
  CellRecs: TList;

procedure CollectCells(e: IInterface);
var
  i: integer;
  c: IInterface;
begin
  for i := 0 to ElementCount(e) - 1 do begin
    c := ElementByIndex(e, i);
    if Signature(c) = 'CELL' then begin
      if ElementExists(c, 'XCLC') then begin
        Cells.Add(IntToStr(GetElementNativeValues(c, 'XCLC\X')) + ',' +
                  IntToStr(GetElementNativeValues(c, 'XCLC\Y')));
        CellRecs.Add(TObject(c));
      end;
    end
    else if ElementType(c) = etGroupRecord then
      CollectCells(c);
  end;
end;

function FindRef(f, stat: IInterface): IInterface;
var
  i: integer;
  r: IInterface;
begin
  Result := nil;
  for i := 0 to ReferencedByCount(stat) - 1 do begin
    r := ReferencedByIndex(stat, i);
    if (Signature(r) = 'REFR') and Equals(GetFile(r), f) then begin
      Result := r;
      Exit;
    end;
  end;
end;

function Initialize: integer;
var
  f, g, wrld, stat, cell, ref: IInterface;
  i, k, made, moved: integer;
  csv, row: TStringList;
  path, edid: string;
begin
  Result := 0;
  f := nil;
  for i := 0 to FileCount - 1 do
    if SameText(GetFileName(FileByIndex(i)), PluginName) then f := FileByIndex(i);
  if not Assigned(f) then begin
    AddMessage(PluginName + ' is not loaded.');
    Result := 1;
    Exit;
  end;

  wrld := MainRecordByEditorID(GroupBySignature(f, 'WRLD'), WorldName);
  if not Assigned(wrld) then begin
    AddMessage('No worldspace ' + WorldName + ' in ' + PluginName + '.');
    Result := 1;
    Exit;
  end;
  Cells := TStringList.Create;
  CellRecs := TList.Create;
  CollectCells(ChildGroup(wrld));
  AddMessage(IntToStr(Cells.Count) + ' cells in ' + WorldName + '.');

  // No dialog: FO4Edit's InputQuery shows its default text as garbage (Chinese characters).
  path := DefaultCsv;
  if not FileExists(path) then begin
    AddMessage('No placement list at ' + path + ' (change DefaultCsv at the top of the script).');
    Result := 1;
    Exit;
  end;
  AddMessage('Reading ' + path);
  csv := TStringList.Create;
  row := TStringList.Create;
  row.Delimiter := ',';
  row.StrictDelimiter := True;
  csv.LoadFromFile(path);

  g := GroupBySignature(f, 'STAT');
  if not Assigned(g) then g := Add(f, 'STAT', True);
  made := 0;
  moved := 0;
  // Columns: n,model,x,y,z,rot_z,cell_x,cell_y,bound_x1,bound_y1,bound_z1,bound_x2,bound_y2,bound_z2
  for i := 1 to csv.Count - 1 do begin
    if Trim(csv[i]) = '' then Continue;
    row.DelimitedText := csv[i];
    edid := 'DevilsBarracks' + Format('%.2d', [StrToInt(row[0])]);

    stat := MainRecordByEditorID(g, edid);
    if not Assigned(stat) then begin
      stat := Add(g, 'STAT', True);
      SetEditValue(Add(stat, 'EDID', True), edid);
    end;
    Add(stat, 'OBND', True);
    SetElementNativeValues(stat, 'OBND\X1', StrToInt(row[8]));
    SetElementNativeValues(stat, 'OBND\Y1', StrToInt(row[9]));
    SetElementNativeValues(stat, 'OBND\Z1', StrToInt(row[10]));
    SetElementNativeValues(stat, 'OBND\X2', StrToInt(row[11]));
    SetElementNativeValues(stat, 'OBND\Y2', StrToInt(row[12]));
    SetElementNativeValues(stat, 'OBND\Z2', StrToInt(row[13]));
    Add(stat, 'Model', True);
    SetElementEditValues(stat, 'Model\MODL', row[1]);

    ref := FindRef(f, stat);
    if Assigned(ref) then
      Inc(moved)
    else begin
      k := Cells.IndexOf(row[6] + ',' + row[7]);
      if k < 0 then begin
        AddMessage(edid + ': no cell ' + row[6] + ',' + row[7] + ' in ' + WorldName + '; skipped.');
        Continue;
      end;
      cell := ObjectToElement(CellRecs[k]);
      ref := Add(cell, 'REFR', True);
      SetElementNativeValues(ref, 'NAME', GetLoadOrderFormID(stat));
      Inc(made);
    end;
    SetElementEditValues(ref, 'DATA\Position\X', row[2]);
    SetElementEditValues(ref, 'DATA\Position\Y', row[3]);
    SetElementEditValues(ref, 'DATA\Position\Z', row[4]);
    SetElementEditValues(ref, 'DATA\Rotation\X', '0');
    SetElementEditValues(ref, 'DATA\Rotation\Y', '0');
    SetElementEditValues(ref, 'DATA\Rotation\Z', row[5]);
  end;
  AddMessage(Format('Barracks: %d placed, %d moved.', [made, moved]));
  csv.Free;
  row.Free;
  Cells.Free;
  CellRecs.Free;
end;

end.
