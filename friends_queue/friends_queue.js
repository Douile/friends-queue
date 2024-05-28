"use strict";

let seekBar = null;
let timeBefore = null;
let timeAfter = null;

function getTimeElms() {
  if (seekBar === null) {
    seekBar = document.querySelector(".seek-bar");
    timeBefore = seekBar.querySelector("span:first-child");
    timeAfter = seekBar.querySelector("span:last-child");
  }
  return [timeBefore, timeAfter];
}

const numberFormatter = new Intl.NumberFormat(undefined, {
  style: "decimal",
  minimumIntegerDigits: 2,
  maximumFractionDigits: 0,
});
function durationToStr(duration) {
  const seconds = duration % 60;
  let minutes = duration / 60;
  const hours = minutes / 60;
  minutes = minutes % 60;
  return `${numberFormatter.format(hours)}:${numberFormatter.format(minutes)}:${numberFormatter.format(seconds)}`;
}

function updateSeekTimes(input) {
  const percent = parseFloat(input.value) / 100;
  const duration = parseFloat(input.dataset.duration);

  const before = duration * percent;

  const [tb, ta] = getTimeElms();
  tb.innerText = durationToStr(before);
  ta.innerText = durationToStr(duration - before);
}
