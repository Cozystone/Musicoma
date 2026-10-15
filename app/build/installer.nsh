; Musicoma — 제거/업데이트 때 사용자 데이터를 지키는 파일 정리 (electron-builder customRemoveFiles)
;
; 설치판의 루트는 $INSTDIR\resources\musicoma 다. 그 아래 sounds(음원 수 GB), projects, renders,
; works, third_party(AI), python-ai 는 사용자가 만든·받은 것이므로 업데이트 때 지우지 않는다.
; 코드(musicoma, ui, engine, setup, .mcp.json)와 앱 파일만 지운다.
; 진짜 제거(업데이트가 아님)일 때는 데이터도 지울지 묻는다(조용한 제거는 남김).

!macro _mcRemoveAllBut DIR KEEP
  FindFirst $R6 $R7 "${DIR}\*.*"
  ${DoWhile} $R7 != ""
    ${If} $R7 != "."
    ${AndIf} $R7 != ".."
    ${AndIf} $R7 != "${KEEP}"
      ${If} ${FileExists} "${DIR}\$R7\*.*"
        RMDir /r "${DIR}\$R7"
      ${Else}
        Delete "${DIR}\$R7"
      ${EndIf}
    ${EndIf}
    FindNext $R6 $R7
  ${Loop}
  FindClose $R6
!macroend

!macro customRemoveFiles
  SetOutPath $TEMP
  StrCpy $R8 "keep"
  ${IfNot} ${isUpdated}
    ${If} ${FileExists} "$INSTDIR\resources\musicoma\sounds\*.*"
    ${OrIf} ${FileExists} "$INSTDIR\resources\musicoma\projects\*.*"
      MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2 "받은 음원·AI 모듈과 프로젝트도 함께 지울까요?$\r$\n$\r$\n(아니오 = 남겨 둠: $INSTDIR\resources\musicoma)" /SD IDNO IDNO mcKeep
        StrCpy $R8 "all"
      mcKeep:
    ${Else}
      StrCpy $R8 "all"
    ${EndIf}
  ${EndIf}

  ${If} $R8 == "all"
    RMDir /r $INSTDIR
  ${Else}
    !insertmacro _mcRemoveAllBut "$INSTDIR" "resources"
    !insertmacro _mcRemoveAllBut "$INSTDIR\resources" "musicoma"
    RMDir /r "$INSTDIR\resources\musicoma\musicoma"
    RMDir /r "$INSTDIR\resources\musicoma\ui"
    RMDir /r "$INSTDIR\resources\musicoma\engine"
    RMDir /r "$INSTDIR\resources\musicoma\setup"
    Delete "$INSTDIR\resources\musicoma\.mcp.json"
    Delete "$INSTDIR\resources\musicoma\THIRD_PARTY_NOTICES.md"
  ${EndIf}
!macroend
