Attribute VB_Name = "POSZONE"

Option Explicit

Private Const MACRO_VERSION As String = "V3.3-SURGICAL-CALLOUT-BORDER-FIX"
Private Const CALLOUT_FRAME_NONE As Long = 0
Private Const CALLOUT_FRAME_CIRCLE As Long = 3
Private Const CALLOUT_FRAME_LEGACY_53 As Long = 53
Private Const CALLOUT_TEXT_PROPERTY_BORDER As Long = 12
' CatTextProperty is zero-based: catFontName = 11 and catBorder = 12.
Private Const CALLOUT_STATUS_IGNORE As Long = 0
Private Const CALLOUT_STATUS_ACCEPTED As Long = 1
Private Const CALLOUT_STATUS_PENDING_GROUP As Long = 2
Private Const CALLOUT_STATUS_PENDING_CONFLICT As Long = 3
Private Const SOURCE_BALLOON As Long = 1
Private Const SOURCE_UNDERLINED As Long = 2
Private Const SOURCE_MULTILINE As Long = 3
Private Const REF_DISTANCE_MIN As Double = 15#
Private Const REF_DISTANCE_MAX As Double = 60#
Private Const REF_DISTANCE_BASE As Double = 35#
Private Const QTY_DISTANCE_MIN As Double = 20#
Private Const QTY_DISTANCE_MAX As Double = 120#
Private Const QTY_DISTANCE_BASE As Double = 70#
Private Const ZONE_MIN_ROWS As Long = 2
Private Const ZONE_MIN_COLS As Long = 3
Private Const ZONE_EDGE_RATIO As Double = 0.12
Private Const ZONE_EDGE_MIN As Double = 15#
Private Const ZONE_EDGE_MAX As Double = 80#
Private Const ZONE_SPACING_ERROR_MAX As Double = 0.25

Private Type ZoneData
    name As String
    x As Double
    y As Double
End Type

Private Type ZoneCandidate
    label As String
    value As Long
    Position As Double
End Type

Private Type ZoneMarker
    label As String
    value As Long
    Position As Double
End Type

Private Type ZoneAxisResult
    IsValid As Boolean
    side As String
    count As Long
    AverageSpacing As Double
    ErrorValue As Double
    score As Double
End Type

Private Type CalloutData
    number As String
    qty As Long
    zone As String
    Sheet As String
    View As String
End Type

Private Type OccurrenceData
    number As String
    qty As Long
    zone As String
    Sheet As String
    View As String
    x As Double
    y As Double
    sourceType As Long
    sourceTextIndex As Long
    sourceLineIndex As Long
    IsReference As Boolean
    HasExplicitQty As Boolean
End Type

Public Sub MapearCalloutsTodasAsFolhas1214()
    Dim oDoc As DrawingDocument
    On Error Resume Next
    Set oDoc = CATIA.ActiveDocument
    On Error GoTo 0
    If oDoc Is Nothing Then
        MsgBox "Nenhum Drawing ativo foi encontrado.", vbExclamation, "Callout Check"
        Exit Sub
    End If

    Dim verdes As New Collection, vermelhos As New Collection
    Dim qtdVerdes As Long, qtdGrupo As Long, qtdConflito As Long
    Dim qtdReferencias As Long, qtdMultiline As Long, falhasCor As Long
    Dim drawingName As String, p As Long
    p = InStrRev(oDoc.name, ".")
    If p > 1 Then drawingName = Left$(oDoc.name, p - 1) Else drawingName = oDoc.name

    Dim xlApp As Object, xlWB As Object, xlWS As Object
    Dim templatePath As String, tempPath As String, outputPath As String
    templatePath = "\\SJKFS17\Mezcal\Projects\OEM\EMB170-190\05. Quality\09. Macros\_Callouts.xlsm"
    If Len(Dir$(templatePath)) = 0 Then
        MsgBox "O template não foi encontrado:" & vbCrLf & vbCrLf & templatePath, vbCritical, "Template não encontrado"
        Exit Sub
    End If
    tempPath = Trim$(Environ$("TEMP"))
    If Len(tempPath) = 0 Then tempPath = Trim$(Environ$("TMP"))
    If Len(tempPath) = 0 Then tempPath = "C:\Temp"
    If Right$(tempPath, 1) <> "\" Then tempPath = tempPath & "\"
    outputPath = ObterCaminhoDisponivel(tempPath, LimparNomeArquivo(drawingName), Format$(Now, "yyyymmdd_hhnnss"))

    On Error GoTo ErroCriarCopia
    FileCopy templatePath, outputPath
    Set xlApp = CreateObject("Excel.Application")
    xlApp.Visible = True
    xlApp.DisplayAlerts = True
    On Error GoTo ErroAbrirExcel
    Set xlWB = xlApp.Workbooks.Open(Filename:=outputPath, UpdateLinks:=False, ReadOnly:=True)
    On Error Resume Next
    Set xlWS = xlWB.Worksheets("Dados_Callouts")
    On Error GoTo ErroAbrirExcel
    If xlWS Is Nothing Then Err.Raise vbObjectError + 2001, "MapearCalloutsTodasAsFolhas121", "A planilha Dados_Callouts não foi encontrada."

    Dim lastRow As Long
    lastRow = xlWS.Cells(xlWS.rows.count, "A").End(-4162).Row
    If lastRow >= 4 Then
        With xlWS.Range("A4:D" & lastRow)
            .ClearContents
            .Interior.Pattern = -4142
            .Font.Color = RGB(0, 0, 0)
        End With
    End If
    With xlWS.Range("A1")
        .value = "PN: " & drawingName
        .Font.name = "Segoe UI": .Font.Size = 14: .Font.Bold = True
        .Font.Color = RGB(255, 255, 255)
        .HorizontalAlignment = -4108: .VerticalAlignment = -4108
    End With

    Dim Occurrences() As OccurrenceData, nOccurrences As Long
    Dim w As Long, oSheet As DrawingSheet
    For w = 1 To oDoc.Sheets.count
        Set oSheet = oDoc.Sheets.Item(w)
        Dim Zonas() As ZoneData, maxZonas As Long
        maxZonas = 0: Erase Zonas
        MapearZonasDaFolha oSheet, Zonas, maxZonas
        ProcessarCalloutsDaFolha oSheet, Zonas, maxZonas, Occurrences, nOccurrences, _
            verdes, vermelhos, qtdVerdes, qtdGrupo, qtdConflito, qtdReferencias, qtdMultiline
    Next w

    Dim Callouts() As CalloutData, nCallouts As Long
    ConsolidarOcorrencias Occurrences, nOccurrences, Callouts, nCallouts

    Dim rowIdx As Long, n As Long, c As Long
    rowIdx = 4
    For n = 1 To nCallouts
        If IsNumeric(Callouts(n).number) Then xlWS.Cells(rowIdx, 1).value = CDbl(Callouts(n).number) Else xlWS.Cells(rowIdx, 1).value = Callouts(n).number
        xlWS.Cells(rowIdx, 2).value = Callouts(n).zone
        xlWS.Cells(rowIdx, 3).value = Callouts(n).qty
        xlWS.Cells(rowIdx, 4).value = Callouts(n).Sheet & " - " & Callouts(n).View
        For c = 1 To 4
            With xlWS.Cells(rowIdx, c)
                .Font.name = "Segoe UI": .Font.Size = 10
                .Borders.LineStyle = 1: .Borders.Color = RGB(217, 217, 217)
                If c <= 3 Then .HorizontalAlignment = -4108
            End With
        Next c
        rowIdx = rowIdx + 1
    Next n
    If rowIdx > 4 Then xlWS.Range("A3:D" & rowIdx - 1).Sort Key1:=xlWS.Range("A4"), Order1:=1, Header:=1
    xlWS.Columns("A:D").AutoFit
    xlWB.Saved = False
    xlWS.Activate
    RestaurarWorkingViewsPrimeiraFolha oDoc

    MsgBox "Macro " & MACRO_VERSION & vbCrLf & _
        "Processamento concluído para o PN " & drawingName & "!" & vbCrLf & vbCrLf & _
        "Objetos válidos identificados: " & qtdVerdes & vbCrLf & _
        "Linhas multilinha contabilizadas: " & qtdMultiline & vbCrLf & _
        "Referências ignoradas por REF: " & qtdReferencias & vbCrLf & _
        "Vermelhos agrupados/ambíguos: " & qtdGrupo & vbCrLf & _
        "Vermelhos inconsistentes: " & qtdConflito & vbCrLf & _
        "Ocorrências válidas encontradas: " & nOccurrences - qtdReferencias & vbCrLf & _
        "Callouts consolidados no Excel: " & nCallouts & vbCrLf & _
        "Falhas ao aplicar cor: " & falhasCor, vbInformation, "Sucesso"
    Exit Sub
ErroCriarCopia:
    MsgBox "Não foi possível criar a cópia temporária:" & vbCrLf & outputPath & vbCrLf & Err.Description, vbCritical, "Erro"
    Exit Sub
ErroAbrirExcel:
    MsgBox "Não foi possível abrir ou preparar a cópia:" & vbCrLf & outputPath & vbCrLf & Err.Description, vbCritical, "Erro"
End Sub

Private Sub ProcessarCalloutsDaFolha(ByVal oSheet As DrawingSheet, ByRef Zonas() As ZoneData, ByVal maxZonas As Long, _
    ByRef Occurrences() As OccurrenceData, ByRef nOccurrences As Long, ByRef verdes As Collection, _
    ByRef vermelhos As Collection, ByRef qtdVerdes As Long, ByRef qtdGrupo As Long, ByRef qtdConflito As Long, _
    ByRef qtdReferencias As Long, ByRef qtdMultiline As Long)
    Dim i As Long, oView As DrawingView
    For i = 1 To oSheet.Views.count
        Set oView = oSheet.Views.Item(i)
        If Not VistaDeveSerIgnorada(oView) Then
            ColetarCalloutsDaVista oSheet, oView, Zonas, maxZonas, Occurrences, nOccurrences, verdes, vermelhos, qtdVerdes, qtdGrupo, qtdConflito, qtdMultiline
            IdentificarReferenciasDaVista oSheet, oView, Occurrences, nOccurrences, qtdReferencias
            AssociarQuantidadesDaVista oSheet, oView, Occurrences, nOccurrences
        End If
    Next i
End Sub

Private Sub ColetarCalloutsDaVista(ByVal oSheet As DrawingSheet, ByVal oView As DrawingView, ByRef Zonas() As ZoneData, _
    ByVal maxZonas As Long, ByRef Occurrences() As OccurrenceData, ByRef nOccurrences As Long, ByRef verdes As Collection, _
    ByRef vermelhos As Collection, ByRef qtdVerdes As Long, ByRef qtdGrupo As Long, ByRef qtdConflito As Long, ByRef qtdMultiline As Long)
    Dim cnt As Long, j As Long, oText As DrawingText, raw As String, linhas() As String, qtdLinhas As Long
    On Error Resume Next: cnt = oView.Texts.count: On Error GoTo 0
    For j = 1 To cnt
        Set oText = Nothing
        On Error Resume Next: Set oText = oView.Texts.Item(j): raw = CStr(oText.Text): On Error GoTo 0
        If Not oText Is Nothing And Len(Trim$(raw)) > 0 Then
            If Not TextoTemREF(raw) And Not TextoTemQuantidade(raw) Then
                SepararTextoEmLinhas raw, linhas, qtdLinhas
                If qtdLinhas > 1 Then
                    ProcessarTextoMultilinha oSheet, oView, oText, j, linhas, qtdLinhas, Zonas, maxZonas, Occurrences, nOccurrences, verdes, qtdVerdes, qtdMultiline
                Else
                    ProcessarTextoSimples oSheet, oView, oText, j, Trim$(raw), Zonas, maxZonas, Occurrences, nOccurrences, verdes, vermelhos, qtdVerdes, qtdGrupo, qtdConflito
                End If
            End If
        End If
    Next j
End Sub

Private Sub ProcessarTextoSimples(ByVal oSheet As DrawingSheet, ByVal oView As DrawingView, ByVal oText As DrawingText, _
    ByVal textIndex As Long, ByVal value As String, ByRef Zonas() As ZoneData, ByVal maxZonas As Long, _
    ByRef Occurrences() As OccurrenceData, ByRef nOccurrences As Long, ByRef verdes As Collection, ByRef vermelhos As Collection, _
    ByRef qtdVerdes As Long, ByRef qtdGrupo As Long, ByRef qtdConflito As Long)
    If Not ContemSomenteDigitosCor(value) Then Exit Sub
    Dim status As Long, mode As String, reason As String, source As Long
    status = ClassificarCalloutParaCor(oText, mode, reason)
    If status = CALLOUT_STATUS_PENDING_GROUP Then AdicionarObjetoSemDuplicar vermelhos, oText: qtdGrupo = qtdGrupo + 1: Exit Sub
    If status = CALLOUT_STATUS_PENDING_CONFLICT Then AdicionarObjetoSemDuplicar vermelhos, oText: qtdConflito = qtdConflito + 1: Exit Sub
    If status = CALLOUT_STATUS_ACCEPTED Then
        source = SOURCE_BALLOON
    ElseIf TextoEstaSublinhado(oText) Then
        source = SOURCE_UNDERLINED
    Else
        Exit Sub
    End If
    Dim x As Double, y As Double, zone As String
    ObterCoordenadaNaFolha oView, oText, x, y
    zone = EncontrarZonaMaisProxima(x, y, Zonas, maxZonas)
    AdicionarOcorrencia Occurrences, nOccurrences, NormalizarNumeroCallout(value), 1, zone, oSheet.name, oView.name, x, y, source, textIndex, 1
    AdicionarObjetoSemDuplicar verdes, oText: qtdVerdes = qtdVerdes + 1
End Sub

Private Sub ProcessarTextoMultilinha(ByVal oSheet As DrawingSheet, ByVal oView As DrawingView, ByVal oText As DrawingText, _
    ByVal textIndex As Long, ByRef linhas() As String, ByVal qtdLinhas As Long, ByRef Zonas() As ZoneData, ByVal maxZonas As Long, _
    ByRef Occurrences() As OccurrenceData, ByRef nOccurrences As Long, ByRef verdes As Collection, ByRef qtdVerdes As Long, ByRef qtdMultiline As Long)
    If Not TextoEstaSublinhado(oText) Then Exit Sub
    Dim x As Double, y As Double, i As Long, numberLine As String, found As Boolean
    ObterCoordenadaNaFolha oView, oText, x, y
    For i = 1 To qtdLinhas
        numberLine = Trim$(linhas(i))
        If ContemSomenteDigitosCor(numberLine) Then
            AdicionarOcorrencia Occurrences, nOccurrences, NormalizarNumeroCallout(numberLine), 1, _
                EncontrarZonaMaisProxima(x, y, Zonas, maxZonas), oSheet.name, oView.name, x, y, SOURCE_MULTILINE, textIndex, i
            qtdMultiline = qtdMultiline + 1: found = True
        End If
    Next i
    If found Then AdicionarObjetoSemDuplicar verdes, oText: qtdVerdes = qtdVerdes + 1
End Sub

Private Sub IdentificarReferenciasDaVista(ByVal oSheet As DrawingSheet, ByVal oView As DrawingView, _
    ByRef Occurrences() As OccurrenceData, ByVal nOccurrences As Long, ByRef qtdReferencias As Long)
    If nOccurrences = 0 Then Exit Sub
    Dim cnt As Long, j As Long, idx As Long, t As DrawingText, s As String, x As Double, y As Double, tol As Double
    On Error Resume Next: cnt = oView.Texts.count: On Error GoTo 0
    tol = ObterToleranciaAdaptativa(oView, REF_DISTANCE_MIN, REF_DISTANCE_MAX, REF_DISTANCE_BASE)
    For j = 1 To cnt
        Set t = Nothing
        On Error Resume Next: Set t = oView.Texts.Item(j): s = CStr(t.Text): On Error GoTo 0
        If Not t Is Nothing And TextoTemREF(s) Then
            ObterCoordenadaNaFolha oView, t, x, y
            For idx = 1 To nOccurrences
                With Occurrences(idx)
                    If .Sheet = oSheet.name And .View = oView.name And Not .IsReference Then
                        If .sourceType = SOURCE_UNDERLINED Or .sourceType = SOURCE_MULTILINE Then
                            If DistanciaEntrePontos(x, y, .x, .y) <= tol Then .IsReference = True: qtdReferencias = qtdReferencias + 1
                        End If
                    End If
                End With
            Next idx
        End If
    Next j
End Sub

Private Sub AssociarQuantidadesDaVista(ByVal oSheet As DrawingSheet, ByVal oView As DrawingView, _
    ByRef Occurrences() As OccurrenceData, ByVal nOccurrences As Long)
    If nOccurrences = 0 Then Exit Sub
    Dim cnt As Long, j As Long, t As DrawingText, s As String, qty As Long, x As Double, y As Double, best As Long
    Dim re As Object: Set re = CreateObject("VBScript.RegExp")
    re.Pattern = "(\d+)": re.Global = False: re.IgnoreCase = True
    On Error Resume Next: cnt = oView.Texts.count: On Error GoTo 0
    Dim tol As Double: tol = ObterToleranciaAdaptativa(oView, QTY_DISTANCE_MIN, QTY_DISTANCE_MAX, QTY_DISTANCE_BASE)
    For j = 1 To cnt
        Set t = Nothing
        On Error Resume Next: Set t = oView.Texts.Item(j): s = UCase$(Trim$(CStr(t.Text))): On Error GoTo 0
        If Not t Is Nothing And TextoTemQuantidade(s) Then
            qty = ExtrairQuantidade(s, re)
            If qty > 0 Then
                ObterCoordenadaNaFolha oView, t, x, y
                best = ProcurarOcorrenciaMaisProxima(oSheet.name, oView.name, x, y, tol, Occurrences, nOccurrences)
                If best > 0 Then Occurrences(best).qty = qty: Occurrences(best).HasExplicitQty = True
            End If
        End If
    Next j
End Sub

Private Function ProcurarOcorrenciaMaisProxima(ByVal sheetName As String, ByVal viewName As String, ByVal x As Double, ByVal y As Double, _
    ByVal maxDistance As Double, ByRef Occurrences() As OccurrenceData, ByVal nOccurrences As Long) As Long
    Dim i As Long, d As Double, minD As Double: minD = 1E+99
    For i = 1 To nOccurrences
        With Occurrences(i)
            If .Sheet = sheetName And .View = viewName And Not .IsReference And Not .HasExplicitQty Then
                d = DistanciaEntrePontos(x, y, .x, .y)
                If d <= maxDistance And d < minD Then minD = d: ProcurarOcorrenciaMaisProxima = i
            End If
        End With
    Next i
End Function

Private Sub ConsolidarOcorrencias(ByRef Occurrences() As OccurrenceData, ByVal nOccurrences As Long, ByRef Callouts() As CalloutData, ByRef nCallouts As Long)
    Dim i As Long, found As Long, zone As String
    For i = 1 To nOccurrences
        If Not Occurrences(i).IsReference Then
            found = LocalizarCalloutPorNumero(Occurrences(i).number, Callouts, nCallouts)
            If Occurrences(i).sourceType = SOURCE_BALLOON Then zone = Occurrences(i).zone Else zone = ""
            If found = 0 Then
                nCallouts = nCallouts + 1: ReDim Preserve Callouts(1 To nCallouts)
                With Callouts(nCallouts)
                    .number = Occurrences(i).number: .qty = Occurrences(i).qty: .zone = zone
                    .Sheet = Occurrences(i).Sheet: .View = Occurrences(i).View
                End With
            Else
                Callouts(found).qty = Callouts(found).qty + Occurrences(i).qty
                If Occurrences(i).sourceType = SOURCE_BALLOON Then
                    If Len(Trim$(Occurrences(i).zone)) > 0 And StrComp(Trim$(Occurrences(i).zone), "N/A", vbTextCompare) <> 0 Then _
                        Callouts(found).zone = AdicionarValorUnico(Callouts(found).zone, Occurrences(i).zone)
                End If
                Callouts(found).Sheet = AdicionarValorUnico(Callouts(found).Sheet, Occurrences(i).Sheet)
                Callouts(found).View = AdicionarValorUnico(Callouts(found).View, Occurrences(i).View)
            End If
        End If
    Next i
End Sub

Private Function LocalizarCalloutPorNumero(ByVal number As String, ByRef Callouts() As CalloutData, ByVal count As Long) As Long
    Dim i As Long
    For i = 1 To count
        If StrComp(Callouts(i).number, number, vbTextCompare) = 0 Then LocalizarCalloutPorNumero = i: Exit Function
    Next i
End Function

Private Function AdicionarValorUnico(ByVal currentList As String, ByVal newValue As String) As String
    currentList = Trim$(currentList): newValue = Trim$(newValue)
    If Len(newValue) = 0 Then AdicionarValorUnico = currentList: Exit Function
    If Len(currentList) = 0 Then AdicionarValorUnico = newValue: Exit Function
    Dim p() As String, i As Long: p = Split(currentList, ";")
    For i = LBound(p) To UBound(p)
        If StrComp(Trim$(p(i)), newValue, vbTextCompare) = 0 Then AdicionarValorUnico = currentList: Exit Function
    Next i
    AdicionarValorUnico = currentList & "; " & newValue
End Function

Private Sub AdicionarOcorrencia(ByRef Occurrences() As OccurrenceData, ByRef count As Long, ByVal number As String, ByVal qty As Long, _
    ByVal zone As String, ByVal sheetName As String, ByVal viewName As String, ByVal x As Double, ByVal y As Double, _
    ByVal source As Long, ByVal textIndex As Long, ByVal lineIndex As Long)
    If Len(number) = 0 Then Exit Sub
    count = count + 1: ReDim Preserve Occurrences(1 To count)
    With Occurrences(count)
        .number = number: If qty > 0 Then .qty = qty Else .qty = 1
        .zone = zone: .Sheet = sheetName: .View = viewName: .x = x: .y = y
        .sourceType = source: .sourceTextIndex = textIndex: .sourceLineIndex = lineIndex
        .IsReference = False: .HasExplicitQty = False
    End With
End Sub

' ===== ZONE ENGINE: BORDER FIRST, AUXILIARY VIEW FALLBACK =====
Private Sub MapearZonasDaFolha(ByVal oSheet As DrawingSheet, ByRef Zonas() As ZoneData, ByRef maxZonas As Long)
    maxZonas = 0: Erase Zonas
    If MapearZonasPelaMargem(oSheet, Zonas, maxZonas) Then Exit Sub
    MapearZonasPelaVistaAuxiliar oSheet, Zonas, maxZonas
End Sub

Private Function MapearZonasPelaMargem(ByVal oSheet As DrawingSheet, ByRef Zonas() As ZoneData, ByRef maxZonas As Long) As Boolean
    Dim width As Double, height As Double: ObterDimensoesFolha oSheet, width, height
    If width <= 0 Or height <= 0 Then Exit Function
    Dim bg As DrawingView: Set bg = ObterBackground(oSheet)
    If bg Is Nothing Then Exit Function
    Dim bandX As Double, bandY As Double
    bandX = Limitar(width * ZONE_EDGE_RATIO, ZONE_EDGE_MIN, ZONE_EDGE_MAX)
    bandY = Limitar(height * ZONE_EDGE_RATIO, ZONE_EDGE_MIN, ZONE_EDGE_MAX)
    Dim L() As ZoneCandidate, r() As ZoneCandidate, t() As ZoneCandidate, b() As ZoneCandidate
    Dim nL As Long, nr As Long, nT As Long, nb As Long
    ColetarMarcadores bg, width, height, bandX, bandY, L, nL, r, nr, t, nT, b, nb
    Dim mL() As ZoneMarker, mR() As ZoneMarker, mT() As ZoneMarker, mB() As ZoneMarker
    Dim cL As Long, cR As Long, cT As Long, cB As Long
    Dim rL As ZoneAxisResult, rR As ZoneAxisResult, rT As ZoneAxisResult, rb As ZoneAxisResult
    ExtrairSequencia L, nL, True, "LEFT", mL, cL, rL
    ExtrairSequencia r, nr, True, "RIGHT", mR, cR, rR
    ExtrairSequencia t, nT, False, "TOP", mT, cT, rT
    ExtrairSequencia b, nb, False, "BOTTOM", mB, cB, rb
    Dim rows() As ZoneMarker
    Dim cols() As ZoneMarker
    Dim rowMarkerCount As Long
    Dim columnMarkerCount As Long

    If Not EscolherEixo( _
            mL, _
            cL, _
            rL, _
            mR, _
            cR, _
            rR, _
            rows, _
            rowMarkerCount) Then

        Exit Function

    End If

    If rb.IsValid Then

        CopiarMarcadores _
            mB, _
            cB, _
            cols, _
            columnMarkerCount

    ElseIf rT.IsValid Then

        CopiarMarcadores _
            mT, _
            cT, _
            cols, _
            columnMarkerCount

    Else

        Exit Function

    End If

    If rowMarkerCount < ZONE_MIN_ROWS Or _
       columnMarkerCount < ZONE_MIN_COLS Then

        Exit Function

    End If

    ConstruirZonas _
        rows, _
        rowMarkerCount, _
        cols, _
        columnMarkerCount, _
        Zonas, _
        maxZonas
    MapearZonasPelaMargem = (maxZonas > 0)
End Function

Private Sub ColetarMarcadores( _
    ByVal bg As DrawingView, _
    ByVal width As Double, _
    ByVal height As Double, _
    ByVal bandX As Double, _
    ByVal bandY As Double, _
    ByRef leftCandidates() As ZoneCandidate, _
    ByRef leftCount As Long, _
    ByRef rightCandidates() As ZoneCandidate, _
    ByRef rightCount As Long, _
    ByRef topCandidates() As ZoneCandidate, _
    ByRef topCount As Long, _
    ByRef bottomCandidates() As ZoneCandidate, _
    ByRef bottomCount As Long)

    Dim textCount As Long
    Dim textIndex As Long
    Dim borderText As DrawingText
    Dim textValue As String
    Dim posX As Double
    Dim posY As Double

    On Error Resume Next
    textCount = bg.Texts.count
    On Error GoTo 0

    For textIndex = 1 To textCount

        Set borderText = Nothing
        textValue = ""

        On Error Resume Next
        Set borderText = bg.Texts.Item(textIndex)

        If Not borderText Is Nothing Then
            textValue = UCase$(Trim$(CStr(borderText.Text)))
        End If

        Err.Clear
        On Error GoTo 0

        If Not borderText Is Nothing Then

            ObterCoordenadaNaFolha _
                bg, _
                borderText, _
                posX, _
                posY

            If EhLetraZona(textValue) Then

                If posX >= 0# And posX <= bandX Then
                    AdicionarCandidato _
                        leftCandidates, _
                        leftCount, _
                        textValue, _
                        Asc(textValue), _
                        posY
                End If

                If posX <= width And posX >= width - bandX Then
                    AdicionarCandidato _
                        rightCandidates, _
                        rightCount, _
                        textValue, _
                        Asc(textValue), _
                        posY
                End If

            ElseIf EhNumeroZona(textValue) Then

                If posY >= height - bandY And posY <= height Then
                    AdicionarCandidato _
                        topCandidates, _
                        topCount, _
                        CStr(CLng(textValue)), _
                        CLng(textValue), _
                        posX
                End If

                If posY >= 0# And posY <= bandY Then
                    AdicionarCandidato _
                        bottomCandidates, _
                        bottomCount, _
                        CStr(CLng(textValue)), _
                        CLng(textValue), _
                        posX
                End If

            End If

        End If

    Next textIndex

End Sub

Private Sub AdicionarCandidato(ByRef a() As ZoneCandidate, ByRef n As Long, ByVal label As String, ByVal value As Long, ByVal pos As Double)
    n = n + 1: ReDim Preserve a(1 To n)
    a(n).label = label: a(n).value = value: a(n).Position = pos
End Sub

Private Sub ExtrairSequencia(ByRef a() As ZoneCandidate, ByVal n As Long, ByVal alpha As Boolean, ByVal side As String, _
    ByRef output() As ZoneMarker, ByRef outCount As Long, ByRef result As ZoneAxisResult)
    result.side = side: result.ErrorValue = 1E+99: result.score = -1E+99
    If n = 0 Then Exit Sub
    OrdenarCandidatos a, n
    Dim minCount As Long: If alpha Then minCount = ZONE_MIN_ROWS Else minCount = ZONE_MIN_COLS
    Dim s As Long, e As Long, cnt As Long, bestS As Long, bestE As Long, bestCount As Long
    Dim avg As Double, errV As Double, score As Double, bestAvg As Double, bestErr As Double
    For s = 1 To n
        For e = s To n
            cnt = e - s + 1
            If cnt >= minCount Then
                If RotulosConsecutivos(a, s, e) Then
                    If EspacamentoValido(a, s, e, avg, errV) Then
                        score = cnt * 1000# - errV * 100#
                        If score > result.score Then bestS = s: bestE = e: bestCount = cnt: bestAvg = avg: bestErr = errV: result.score = score
                    End If
                End If
            End If
        Next e
    Next s
    If bestCount = 0 Then Exit Sub
    ReDim output(1 To bestCount)
    Dim i As Long, k As Long
    For i = bestS To bestE
        k = k + 1: output(k).label = a(i).label: output(k).value = a(i).value: output(k).Position = a(i).Position
    Next i
    outCount = bestCount: result.IsValid = True: result.count = bestCount: result.AverageSpacing = bestAvg: result.ErrorValue = bestErr
End Sub

Private Function RotulosConsecutivos(ByRef a() As ZoneCandidate, ByVal s As Long, ByVal e As Long) As Boolean
    If e <= s Then Exit Function
    Dim direction As Long, i As Long
    direction = a(s + 1).value - a(s).value
    If Abs(direction) <> 1 Then Exit Function
    For i = s To e - 1
        If a(i + 1).value - a(i).value <> direction Then Exit Function
    Next i
    RotulosConsecutivos = True
End Function

Private Function EspacamentoValido(ByRef a() As ZoneCandidate, ByVal s As Long, ByVal e As Long, ByRef avg As Double, ByRef meanErr As Double) As Boolean
    Dim i As Long, intervals As Long, d As Double, total As Double, maxErr As Double, er As Double
    intervals = e - s: If intervals <= 0 Then Exit Function
    For i = s To e - 1
        d = Abs(a(i + 1).Position - a(i).Position): If d <= 0.001 Then Exit Function
        total = total + d
    Next i
    avg = total / intervals
    For i = s To e - 1
        d = Abs(a(i + 1).Position - a(i).Position)
        er = Abs(d - avg) / avg: meanErr = meanErr + er: If er > maxErr Then maxErr = er
    Next i
    meanErr = meanErr / intervals
    EspacamentoValido = (maxErr <= ZONE_SPACING_ERROR_MAX)
End Function

Private Function EscolherEixo(ByRef a() As ZoneMarker, ByVal na As Long, ByRef ra As ZoneAxisResult, _
    ByRef b() As ZoneMarker, ByVal nb As Long, ByRef rb As ZoneAxisResult, ByRef output() As ZoneMarker, ByRef no As Long) As Boolean
    If Not ra.IsValid And Not rb.IsValid Then Exit Function
    If ra.IsValid And (Not rb.IsValid Or ra.score >= rb.score) Then CopiarMarcadores a, na, output, no Else CopiarMarcadores b, nb, output, no
    EscolherEixo = True
End Function

Private Sub ConstruirZonas(ByRef rows() As ZoneMarker, ByVal nr As Long, ByRef cols() As ZoneMarker, ByVal nc As Long, _
    ByRef zones() As ZoneData, ByRef nz As Long)
    Dim r As Long, c As Long
    For r = 1 To nr
        For c = 1 To nc
            nz = nz + 1: ReDim Preserve zones(1 To nz)
            zones(nz).name = UCase$(rows(r).label) & Format$(cols(c).value, "000")
            zones(nz).x = cols(c).Position: zones(nz).y = rows(r).Position
        Next c
    Next r
End Sub

Private Sub MapearZonasPelaVistaAuxiliar(ByVal oSheet As DrawingSheet, ByRef zones() As ZoneData, ByRef nz As Long)
    nz = 0: Erase zones
    Dim i As Long, j As Long, v As DrawingView, t As DrawingText, s As String, normalized As String, x As Double, y As Double
    For i = 1 To oSheet.Views.count
        Set v = oSheet.Views.Item(i)
        If EhVistaAuxiliar(v) Then
            For j = 1 To v.Texts.count
                Set t = v.Texts.Item(j): s = CStr(t.Text)
                If NormalizarZonaAuxiliar(s, normalized) Then
                    ObterCoordenadaNaFolha v, t, x, y
                    nz = nz + 1: ReDim Preserve zones(1 To nz)
                    zones(nz).name = normalized: zones(nz).x = x: zones(nz).y = y
                End If
            Next j
            If nz > 0 Then Exit Sub
        End If
    Next i
End Sub

Private Function NormalizarZonaAuxiliar(ByVal s As String, ByRef result As String) As Boolean
    s = UCase$(Trim$(s)): result = ""
    If Len(s) < 2 Or Len(s) > 4 Then Exit Function
    If Not EhLetraZona(Left$(s, 1)) Or Not ContemSomenteDigitosCor(Mid$(s, 2)) Then Exit Function
    Dim n As Long: n = CLng(Mid$(s, 2)): If n <= 0 Or n > 999 Then Exit Function
    result = Left$(s, 1) & Format$(n, "000"): NormalizarZonaAuxiliar = True
End Function

Private Function EncontrarZonaMaisProxima(ByVal x As Double, ByVal y As Double, ByRef zones() As ZoneData, ByVal n As Long) As String
    EncontrarZonaMaisProxima = "N/A": If n = 0 Then Exit Function
    Dim i As Long, d As Double, minD As Double: minD = 1E+99
    For i = 1 To n
        d = DistanciaEntrePontos(x, y, zones(i).x, zones(i).y)
        If d < minD Then minD = d: EncontrarZonaMaisProxima = zones(i).name
    Next i
End Function

Private Function ObterBackground(ByVal s As DrawingSheet) As DrawingView
    Dim i As Long, v As DrawingView
    For i = 1 To s.Views.count
        Set v = s.Views.Item(i)
        If v.ViewType = catViewBackground Then Set ObterBackground = v: Exit Function
    Next i
End Function

Private Sub ObterDimensoesFolha(ByVal s As DrawingSheet, ByRef width As Double, ByRef height As Double)
    On Error Resume Next: width = CDbl(s.GetPaperWidth): height = CDbl(s.GetPaperHeight): On Error GoTo 0
End Sub

Private Function EhLetraZona(ByVal s As String) As Boolean
    s = UCase$(Trim$(s)): EhLetraZona = (Len(s) = 1 And s >= "A" And s <= "F")
End Function

Private Function EhNumeroZona(ByVal s As String) As Boolean
    If Not ContemSomenteDigitosCor(s) Or Len(Trim$(s)) > 3 Then Exit Function
    Dim n As Long: n = CLng(Trim$(s)): EhNumeroZona = (n > 0 And n <= 999)
End Function

Private Sub OrdenarCandidatos(ByRef a() As ZoneCandidate, ByVal n As Long)
    Dim i As Long, j As Long, tmp As ZoneCandidate
    For i = 1 To n - 1
        For j = i + 1 To n
            If a(j).Position < a(i).Position Then tmp = a(i): a(i) = a(j): a(j) = tmp
        Next j
    Next i
End Sub

Private Sub CopiarMarcadores(ByRef src() As ZoneMarker, ByVal n As Long, ByRef dst() As ZoneMarker, ByRef nd As Long)
    If n = 0 Then Exit Sub
    ReDim dst(1 To n): Dim i As Long
    For i = 1 To n: dst(i) = src(i): Next i
    nd = n
End Sub

Private Function Limitar(ByVal v As Double, ByVal minV As Double, ByVal maxV As Double) As Double
    If v < minV Then v = minV
    If v > maxV Then v = maxV
    Limitar = v
End Function

Private Function EhVistaAuxiliar(ByVal v As DrawingView) As Boolean
    Dim s As String: s = UCase$(Trim$(v.name))
    EhVistaAuxiliar = (s = "ZONE" Or Left$(s, 5) = "ZONE[" Or Left$(s, Len("ZONES_A1_SHT")) = "ZONES_A1_SHT")
End Function

' ===== ORIGINAL CALLOUT CLASSIFICATION =====
Private Function ClassificarCalloutParaCor(ByVal oText As Object, ByRef detectionMode As String, ByRef reason As String) As Long
    Dim s As String, gf As Long, inf As Long, gr As Boolean, ir As Boolean
    detectionMode = "": reason = "": If oText Is Nothing Then Exit Function
    On Error Resume Next: s = Trim$(CStr(oText.Text)): If Err.number <> 0 Then Err.Clear: On Error GoTo 0: Exit Function
    On Error GoTo 0: If Not ContemSomenteDigitosCor(s) Then Exit Function
    gf = LerFrameGlobalCor(oText, gr): inf = LerFrameInternoCor(oText, Len(s), ir)
    If gr And (gf = CALLOUT_FRAME_CIRCLE Or gf = CALLOUT_FRAME_LEGACY_53) And Len(s) <= 4 Then detectionMode = "GLOBAL_CIRCLE": ClassificarCalloutParaCor = CALLOUT_STATUS_ACCEPTED: Exit Function
    If gr And ir Then
        If gf = CALLOUT_FRAME_NONE And (inf = CALLOUT_FRAME_CIRCLE Or inf = CALLOUT_FRAME_LEGACY_53) Then
            If Len(s) <= 3 Then detectionMode = "INTERNAL_CIRCLE": ClassificarCalloutParaCor = CALLOUT_STATUS_ACCEPTED Else reason = "Grupo ou callout ambíguo não contabilizado.": ClassificarCalloutParaCor = CALLOUT_STATUS_PENDING_GROUP
            Exit Function
        End If
        If gf <> CALLOUT_FRAME_NONE And gf <> CALLOUT_FRAME_CIRCLE And gf <> CALLOUT_FRAME_LEGACY_53 And _
           (inf = CALLOUT_FRAME_CIRCLE Or inf = CALLOUT_FRAME_LEGACY_53) Then reason = "Inconsistência de frame não contabilizada.": ClassificarCalloutParaCor = CALLOUT_STATUS_PENDING_CONFLICT
    End If
End Function

Private Function LerFrameGlobalCor(ByVal t As Object, ByRef success As Boolean) As Long
    Dim v As Variant: On Error Resume Next: v = t.FrameType
    If Err.number = 0 And IsNumeric(v) Then LerFrameGlobalCor = CLng(v): success = True
    Err.Clear: On Error GoTo 0
End Function

Private Function LerFrameInternoCor(ByVal t As Object, ByVal n As Long, ByRef success As Boolean) As Long
    If n <= 0 Then Exit Function
    Dim v As Variant: On Error Resume Next: v = t.GetParameterOnSubString(CALLOUT_TEXT_PROPERTY_BORDER, 0, n)
    If Err.number = 0 And IsNumeric(v) Then LerFrameInternoCor = CLng(v): success = True
    Err.Clear: On Error GoTo 0
End Function

Private Function TextoEstaSublinhado(ByVal t As Object) As Boolean
    Dim p As Object: On Error Resume Next: Set p = t.TextProperties
    If Not p Is Nothing Then TextoEstaSublinhado = (CLng(p.Underline) = 1)
    Err.Clear: On Error GoTo 0
End Function

Private Sub ObterCoordenadaNaFolha(ByVal v As DrawingView, ByVal t As DrawingText, ByRef x As Double, ByRef y As Double)
    Dim a As Double, sc As Double: On Error Resume Next: a = CDbl(v.Angle): On Error GoTo 0: sc = ObterEscalaSegura(v)
    If Abs(a) > 0.001 Then
        x = v.x + t.x * sc * Cos(a) - t.y * sc * Sin(a)
        y = v.y + t.x * sc * Sin(a) + t.y * sc * Cos(a)
    Else
        x = v.x + t.x * sc: y = v.y + t.y * sc
    End If
End Sub

Private Function ObterEscalaSegura(ByVal v As DrawingView) As Double
    Dim sc As Double: On Error Resume Next: sc = CDbl(v.Scale2)
    If Err.number <> 0 Or sc <= 0 Then Err.Clear: sc = CDbl(v.Scale)
    Err.Clear: On Error GoTo 0: If sc <= 0 Then sc = 1
    ObterEscalaSegura = sc
End Function

Private Function ObterToleranciaAdaptativa(ByVal v As DrawingView, ByVal minV As Double, ByVal maxV As Double, ByVal baseV As Double) As Double
    Dim r As Double: r = baseV * Sqr(ObterEscalaSegura(v)): If r < minV Then r = minV: If r > maxV Then r = maxV
    ObterToleranciaAdaptativa = r
End Function

Private Function DistanciaEntrePontos(ByVal x1 As Double, ByVal y1 As Double, ByVal x2 As Double, ByVal y2 As Double) As Double
    DistanciaEntrePontos = Sqr((x1 - x2) ^ 2 + (y1 - y2) ^ 2)
End Function

Private Sub SepararTextoEmLinhas(ByVal s As String, ByRef lines() As String, ByRef n As Long)
    s = Replace(s, vbCrLf, vbLf): s = Replace(s, vbCr, vbLf)
    Dim p() As String, i As Long: p = Split(s, vbLf): n = UBound(p) - LBound(p) + 1: ReDim lines(1 To n)
    For i = 1 To n: lines(i) = p(LBound(p) + i - 1): Next i
End Sub

Private Function TextoTemREF(ByVal s As String) As Boolean: TextoTemREF = InStr(1, s, "REF", vbTextCompare) > 0: End Function
Private Function TextoTemQuantidade(ByVal s As String) As Boolean: s = UCase$(Trim$(s)): TextoTemQuantidade = (InStr(1, s, "REQD", vbTextCompare) > 0 Or InStr(1, s, "PL", vbTextCompare) > 0): End Function

Private Function ExtrairQuantidade(ByVal s As String, ByVal re As Object) As Long
    If re Is Nothing Or Not re.Test(s) Then Exit Function
    On Error Resume Next: ExtrairQuantidade = CLng(re.Execute(s)(0).SubMatches(0)): If Err.number <> 0 Then ExtrairQuantidade = 0
    Err.Clear: On Error GoTo 0
End Function

Private Function ContemSomenteDigitosCor(ByVal s As String) As Boolean
    s = Trim$(s): If Len(s) = 0 Then Exit Function
    Dim i As Long, ch As String
    For i = 1 To Len(s): ch = Mid$(s, i, 1): If ch < "0" Or ch > "9" Then Exit Function
    Next i: ContemSomenteDigitosCor = True
End Function

Private Function NormalizarNumeroCallout(ByVal s As String) As String
    s = Trim$(s): If Not ContemSomenteDigitosCor(s) Then NormalizarNumeroCallout = s: Exit Function
    Do While Len(s) > 1 And Left$(s, 1) = "0": s = Mid$(s, 2): Loop
    NormalizarNumeroCallout = s
End Function

Private Function VistaDeveSerIgnorada(ByVal v As DrawingView) As Boolean
    If v Is Nothing Then VistaDeveSerIgnorada = True: Exit Function
    If v.ViewType = catViewBackground Or EhVistaAuxiliar(v) Then VistaDeveSerIgnorada = True
End Function

Private Sub AdicionarObjetoSemDuplicar(ByRef objects As Collection, ByVal obj As Object)
    If objects Is Nothing Or obj Is Nothing Then Exit Sub
    Dim i As Long: For i = 1 To objects.count: If objects.Item(i) Is obj Then Exit Sub
    Next i: objects.Add obj
End Sub

Private Function AplicarCorEmLote(ByVal doc As Object, ByVal objects As Collection, ByVal r As Long, ByVal g As Long, ByVal b As Long) As Boolean
    If doc Is Nothing Or objects Is Nothing Then Exit Function
    If objects.count = 0 Then Exit Function
    Dim sel As Object, vis As Object, i As Long: Set sel = doc.Selection: sel.Clear
    On Error Resume Next: For i = 1 To objects.count: sel.Add objects.Item(i): Next i
    Set vis = sel.VisProperties: vis.SetRealColor r, g, b, 1: AplicarCorEmLote = (Err.number = 0): Err.Clear: sel.Clear: On Error GoTo 0
End Function

Private Function LimparNomeArquivo(ByVal s As String) As String
    Dim invalid As Variant, x As Variant: invalid = Array("\", "/", ":", "*", "?", Chr$(34), "<", ">", "|")
    s = Trim$(s): For Each x In invalid: s = Replace(s, CStr(x), "_"): Next x
    If Len(s) = 0 Then s = "Drawing": LimparNomeArquivo = s
End Function

Private Function ObterCaminhoDisponivel(ByVal folder As String, ByVal name As String, ByVal stamp As String) As String
    Dim path As String, i As Long: path = folder & name & "_Callouts_" & stamp & ".xlsm": i = 1
    Do While Len(Dir$(path)) > 0: path = folder & name & "_Callouts_" & stamp & "_" & Format$(i, "000") & ".xlsm": i = i + 1: Loop
    ObterCaminhoDisponivel = path
End Function

Public Sub AbrirFontCheck(): frmE1Tools.Show: End Sub

Private Sub RestaurarWorkingViewsPrimeiraFolha(ByVal doc As DrawingDocument)
    If doc Is Nothing Or doc.Sheets.count = 0 Then Exit Sub
    Dim s As DrawingSheet, v As DrawingView, i As Long: Set s = doc.Sheets.Item(1)
    On Error Resume Next: s.Activate: On Error GoTo 0
    For i = 1 To s.Views.count
        Set v = s.Views.Item(i)
        If Not VistaDeveSerIgnorada(v) Then
            On Error Resume Next
            v.Activate
            If Err.number = 0 Then
                On Error GoTo 0
                Exit For
            End If
            Err.Clear
            On Error GoTo 0
        End If
    Next i
    On Error Resume Next: CATIA.ActiveWindow.ActiveViewer.Update: On Error GoTo 0
End Sub

