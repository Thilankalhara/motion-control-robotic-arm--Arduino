#include <Servo.h>

Servo base, shoulder, elbow, gripper;

// Current positions (float for smooth interpolation)
float curBase     = 90;
float curShoulder = 90;
float curElbow    = 90;
float curGripper  = 0;

// Target positions — servos glide toward these
float tgtBase     = 90;
float tgtShoulder = 90;
float tgtElbow    = 90;
float tgtGripper  = 0;

// Smoothing speed (0.05 = slow/smooth, 0.20 = fast/snappy)
float smoothBase     = 0.08;
float smoothShoulder = 0.08;
float smoothElbow    = 0.08;
float smoothGripper  = 0.15;

// True while servos are attached and receiving PWM signal
bool attached = true;

unsigned long lastMove = 0;

// ─────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);
  attachAll();

  // Smooth startup sweep to home position
  for (int i = 0; i <= 90; i++) {
    base.write(i);
    shoulder.write(i);
    elbow.write(i);
    delay(8);
  }
  gripper.write(0);

  Serial.println("ARM READY");
}

// ─────────────────────────────────────────────────────────────
void loop() {

  // ── READ SERIAL COMMAND ───────────────────────────────────
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() == 0) return;

    // ── DETACH: cut PWM signal → motors draw zero current → no heat
    if (cmd == "DETACH") {
      detachAll();
      Serial.println("DETACHED");
      return;
    }

    // ── ATTACH: re-enable PWM so servos can move again
    if (cmd == "ATTACH") {
      attachAll();
      // Write current positions immediately so arm doesn't jerk
      base.write((int)curBase);
      shoulder.write((int)curShoulder);
      elbow.write((int)curElbow);
      gripper.write((int)curGripper);
      Serial.println("ATTACHED");
      return;
    }

    // ── NORMAL MOVE COMMAND: B<angle> S<angle> E<angle> G<angle>
    // If servos were detached, re-attach first
    if (!attached) {
      attachAll();
      base.write((int)curBase);
      shoulder.write((int)curShoulder);
      elbow.write((int)curElbow);
      gripper.write((int)curGripper);
    }

    int b = getValue(cmd, 'B');
    int s = getValue(cmd, 'S');
    int e = getValue(cmd, 'E');
    int g = getValue(cmd, 'G');

    // Only update targets that are present in the command
    // This is the KEY FIX: if a value is missing (-1), the servo
    // holds its last target — it does NOT go slack or droop.
    if (b >= 0) tgtBase     = constrain(b, 0,  180);
    if (s >= 0) tgtShoulder = constrain(s, 30, 150);
    if (e >= 0) tgtElbow    = constrain(e, 0,  160);
    if (g >= 0) tgtGripper  = constrain(g, 0,  60);
  }

  // ── SMOOTH LERP every 20ms ────────────────────────────────
  // Runs continuously regardless of incoming commands.
  // This means every servo always holds its target position —
  // even if no new command came in this loop cycle.
  if (millis() - lastMove >= 20) {
    lastMove = millis();

    if (attached) {
      curBase     += (tgtBase     - curBase)     * smoothBase;
      curShoulder += (tgtShoulder - curShoulder) * smoothShoulder;
      curElbow    += (tgtElbow    - curElbow)     * smoothElbow;
      curGripper  += (tgtGripper  - curGripper)  * smoothGripper;

      base.write((int)curBase);
      shoulder.write((int)curShoulder);
      elbow.write((int)curElbow);
      gripper.write((int)curGripper);
    }
  }
}

// ─────────────────────────────────────────────────────────────
//  ATTACH / DETACH HELPERS
// ─────────────────────────────────────────────────────────────

void attachAll() {
  base.attach(9);
  shoulder.attach(10);
  elbow.attach(11);
  gripper.attach(6);
  attached = true;
}

void detachAll() {
  // Write final position before detaching so arm rests there cleanly
  base.write((int)curBase);
  shoulder.write((int)curShoulder);
  elbow.write((int)curElbow);
  gripper.write((int)curGripper);
  delay(300);  // give servos time to reach position

  base.detach();
  shoulder.detach();
  elbow.detach();
  gripper.detach();
  attached = false;
}

// ─────────────────────────────────────────────────────────────
//  PARSE VALUE from command string e.g. getValue("B90 S45", 'S') → 45
//  Returns -1 if prefix not found (means: keep last target, don't change)
// ─────────────────────────────────────────────────────────────
int getValue(String data, char prefix) {
  int idx = data.indexOf(prefix);
  if (idx == -1) return -1;
  return data.substring(idx + 1).toInt();
}
