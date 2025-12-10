import XCTest
@testable import MinnetsMac

/// Tests for PermissionManager.PermissionStatus
final class PermissionManagerTests: XCTestCase {
    
    // MARK: - PermissionStatus Tests
    
    func testPermissionStatus_IsGranted() {
        XCTAssertTrue(PermissionManager.PermissionStatus.granted.isGranted)
        XCTAssertFalse(PermissionManager.PermissionStatus.denied.isGranted)
        XCTAssertFalse(PermissionManager.PermissionStatus.unknown.isGranted)
    }
    
    func testPermissionStatus_DisplayText() {
        XCTAssertEqual(PermissionManager.PermissionStatus.granted.displayText, "Granted")
        XCTAssertEqual(PermissionManager.PermissionStatus.denied.displayText, "Not Granted")
        XCTAssertEqual(PermissionManager.PermissionStatus.unknown.displayText, "Checking...")
    }
    
    func testPermissionStatus_SymbolName() {
        XCTAssertEqual(PermissionManager.PermissionStatus.granted.symbolName, "checkmark.circle.fill")
        XCTAssertEqual(PermissionManager.PermissionStatus.denied.symbolName, "xmark.circle.fill")
        XCTAssertEqual(PermissionManager.PermissionStatus.unknown.symbolName, "questionmark.circle")
    }
    
    func testPermissionStatus_Equality() {
        XCTAssertEqual(PermissionManager.PermissionStatus.granted, .granted)
        XCTAssertEqual(PermissionManager.PermissionStatus.denied, .denied)
        XCTAssertEqual(PermissionManager.PermissionStatus.unknown, .unknown)
        XCTAssertNotEqual(PermissionManager.PermissionStatus.granted, .denied)
    }
}
