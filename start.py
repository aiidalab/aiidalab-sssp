# -*- coding: utf-8 -*-

import ipywidgets as ipw

template = """
<table>
<tr>
  <td valign="top"><ul>
    <a href="{appbase}/qe.ipynb" target="_blank">
        <img src="https://raw.githubusercontent.com/aiidalab/aiidalab-sssp/main/miscellaneous/logo-sssp.png" height="120px" width=243px">
    </a>
  </ul></td>
  <td valign="top"><ul>
    <li><a href="{appbase}/verification.ipynb" target="_blank">Running SSSP Verification </a></li>
    <li><a href="{appbase}/inspect.ipynb" target="_blank"> Inspect and Compare Verification Results </a></li>
  </ul></td>
</tr>
</table>
"""


def get_start_widget(appbase, jupbase, notebase):
    html = template.format(appbase=appbase, jupbase=jupbase, notebase=notebase)
    return ipw.HTML(html)


#EOF
