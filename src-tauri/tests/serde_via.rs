use jumptunnel_lib::tunnel::TunnelStatus;

#[derive(serde::Serialize)]
struct Event {
    id: String,
    status: TunnelStatus,
}

#[test]
fn running_status_includes_via() {
    let ev = Event {
        id: "m1".into(),
        status: TunnelStatus::Running {
            actual_port: 13082,
            via: "simsadmin@10.2.68.128:51730".into(),
        },
    };
    let json = serde_json::to_string(&ev).unwrap();
    println!("serialized: {json}");
    assert!(json.contains("\"actualPort\":13082"), "actualPort field: {json}");
    assert!(json.contains("\"via\":\"simsadmin@10.2.68.128:51730\""), "via field: {json}");
    assert!(json.contains("\"state\":\"running\""), "state tag: {json}");
}
