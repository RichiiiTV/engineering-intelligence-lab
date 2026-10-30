(* Generated text only: DriveEnable Antriebsfreigabe; StopLatch Stoppverriegelung *)
IF stop_request THEN
    drive_enable := FALSE;
END_IF;
(* The missing re-enable branch is a question to investigate, not proof of a defect. *)