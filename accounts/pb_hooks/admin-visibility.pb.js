/// <reference path="../pb_data/types.d.ts" />
// List/view rules alone do not expose auth emails when emailVisibility is false.
// Approvals need those addresses. Do not grant manageRule (it bypasses update rules).
onRecordEnrich((e) => {
  e.next();
  const auth = e.requestInfo && e.requestInfo.auth;
  if (auth && auth.collection().name === "users" && auth.getBool("admin")) {
    e.record.ignoreEmailVisibility(true);
  }
}, "users");
